/**
 * Server-sent event parsing for the playlist generation stream.
 *
 * The previous implementation decoded each network chunk in isolation and split
 * it on newlines, so any `data:` line that straddled a chunk boundary produced
 * invalid JSON and was dropped. On a large playlist that could lose track_found
 * events or, worse, the final `complete` event. This keeps a buffer across
 * chunks and only emits whole frames.
 */

/**
 * Read an SSE response body, yielding each parsed event object.
 *
 * @param {Response} response - a fetch Response with a readable body
 * @returns {AsyncGenerator<object>} parsed event payloads
 */
export async function* readEventStream(response) {
  if (!response.body) {
    throw new Error('Streaming is not supported in this browser');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    for (;;) {
      const { done, value } = await reader.read();

      if (done) {
        // Flush whatever the decoder is still holding, then emit any final
        // frame that arrived without a trailing blank line.
        buffer += decoder.decode();
        const last = parseFrame(buffer);
        if (last) yield last;
        return;
      }

      // stream: true keeps multi-byte characters split across chunks intact.
      buffer += decoder.decode(value, { stream: true });

      // Frames are separated by a blank line. Anything after the final
      // separator is incomplete and stays in the buffer for the next chunk.
      const frames = buffer.split('\n\n');
      buffer = frames.pop() ?? '';

      for (const frame of frames) {
        const event = parseFrame(frame);
        if (event) yield event;
      }
    }
  } finally {
    reader.releaseLock();
  }
}

/**
 * Turn one raw SSE frame into an object, or null if it holds no usable data.
 */
function parseFrame(frame) {
  if (!frame || !frame.trim()) return null;

  // A frame may carry several data: lines, which concatenate.
  const data = frame
    .split('\n')
    .filter((line) => line.startsWith('data:'))
    .map((line) => line.slice(5).trim())
    .join('');

  if (!data) return null;

  try {
    return JSON.parse(data);
  } catch {
    console.warn('Discarding malformed SSE frame', data.slice(0, 200));
    return null;
  }
}
