import { useCallback, useEffect, useRef, useState } from 'react';

import { API_BASE_URL, authHeader } from '../config';
import { readEventStream } from '../lib/sse';

const PASSES = ['analyze', 'generate', 'validate', 'search'];

const initialProgress = () =>
  PASSES.reduce((acc, pass) => ({ ...acc, [pass]: 'pending' }), {});

/**
 * Drives playlist generation over the SSE endpoint.
 *
 * Deliberately has no silent fallback to the non-streaming endpoint. The old
 * code re-ran the entire generation whenever the stream hiccuped, which
 * doubled the OpenAI and Spotify cost of every failure and hid the cause. A
 * failure now surfaces so the user can retry knowingly.
 */
export function useStreamingGeneration() {
  const [status, setStatus] = useState('idle'); // idle | streaming | done | error
  const [statusMessage, setStatusMessage] = useState('');
  const [currentPass, setCurrentPass] = useState(null);
  const [passProgress, setPassProgress] = useState(initialProgress);
  const [foundTracks, setFoundTracks] = useState([]);
  const [playlist, setPlaylist] = useState(null);
  const [partial, setPartial] = useState(null);
  const [error, setError] = useState(null);

  const abortRef = useRef(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      abortRef.current?.abort();
    };
  }, []);

  const reset = useCallback(() => {
    setStatus('idle');
    setStatusMessage('');
    setCurrentPass(null);
    setPassProgress(initialProgress());
    setFoundTracks([]);
    setPlaylist(null);
    setPartial(null);
    setError(null);
  }, []);

  const cancel = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    if (mountedRef.current) {
      setStatus('idle');
      setStatusMessage('');
    }
  }, []);

  const generate = useCallback(async (query, trackCount) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setStatus('streaming');
    setStatusMessage('Starting…');
    setCurrentPass(null);
    setPassProgress(initialProgress());
    setFoundTracks([]);
    setPlaylist(null);
    setPartial(null);
    setError(null);

    try {
      const response = await fetch(`${API_BASE_URL}/api/generate-playlist-stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...(await authHeader()) },
        body: JSON.stringify({ query, track_count: trackCount }),
        signal: controller.signal,
      });

      if (response.status === 401) {
        throw Object.assign(new Error('Your Spotify session has expired.'), { isAuthError: true });
      }
      if (!response.ok) {
        throw new Error('Could not start playlist generation. Please try again.');
      }

      for await (const event of readEventStream(response)) {
        if (!mountedRef.current) return null;

        switch (event.type) {
          case 'pass_start':
            setCurrentPass(event.pass);
            setPassProgress((prev) => ({ ...prev, [event.pass]: 'active' }));
            setStatusMessage(event.message ?? '');
            break;

          case 'pass_progress':
            setStatusMessage(event.message ?? '');
            break;

          case 'pass_complete':
            setPassProgress((prev) => ({ ...prev, [event.pass]: 'complete' }));
            setStatusMessage(event.message ?? '');
            break;

          case 'track_found':
            setFoundTracks((prev) => [...prev, event.track]);
            break;

          case 'status':
            setStatusMessage(event.message ?? '');
            break;

          case 'partial':
            setPartial({ requested: event.requested, found: event.found, message: event.message });
            break;

          case 'complete':
            setPlaylist(event.playlist);
            setStatus('done');
            return event.playlist;

          case 'error':
            // The server reported a real failure. This used to be thrown inside
            // a try whose catch only logged a warning, so the user was dropped
            // back to the form with no explanation at all.
            throw new Error(event.message || 'Playlist generation failed.');

          default:
            break;
        }
      }

      // Stream ended without a complete event.
      throw new Error('The connection ended before your playlist was ready.');
    } catch (err) {
      if (err.name === 'AbortError') return null;
      if (mountedRef.current) {
        setStatus('error');
        setError({ message: err.message, isAuthError: Boolean(err.isAuthError) });
      }
      return null;
    } finally {
      if (abortRef.current === controller) abortRef.current = null;
    }
  }, []);

  return {
    status,
    statusMessage,
    currentPass,
    passProgress,
    foundTracks,
    playlist,
    partial,
    error,
    generate,
    cancel,
    reset,
  };
}
