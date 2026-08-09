import { readEventStream } from '../sse';

/**
 * Build a fake Response whose body yields the given byte chunks, so a stream
 * can be split at arbitrary points.
 */
function mockResponse(chunks) {
  const encoder = new TextEncoder();
  const encoded = chunks.map((c) => encoder.encode(c));
  let i = 0;

  return {
    body: {
      getReader: () => ({
        read: async () =>
          i < encoded.length ? { done: false, value: encoded[i++] } : { done: true, value: undefined },
        releaseLock: () => {},
      }),
    },
  };
}

async function collect(chunks) {
  const events = [];
  for await (const event of readEventStream(mockResponse(chunks))) {
    events.push(event);
  }
  return events;
}

describe('readEventStream', () => {
  it('parses whole frames', async () => {
    const events = await collect([
      'data: {"type":"pass_start","pass":"analyze"}\n\n',
      'data: {"type":"complete","playlist":{"tracks":[]}}\n\n',
    ]);

    expect(events).toHaveLength(2);
    expect(events[0].type).toBe('pass_start');
    expect(events[1].type).toBe('complete');
  });

  it('reassembles a frame split across chunk boundaries', async () => {
    // The original implementation decoded each chunk independently, so a frame
    // broken like this was discarded as malformed JSON.
    const events = await collect([
      'data: {"type":"track_f',
      'ound","track":{"title":"Holocene"',
      '}}\n\n',
    ]);

    expect(events).toHaveLength(1);
    expect(events[0].type).toBe('track_found');
    expect(events[0].track.title).toBe('Holocene');
  });

  it('does not lose the final event when the separator is split', async () => {
    const events = await collect([
      'data: {"type":"a"}\n',
      '\ndata: {"type":"complete"}\n\n',
    ]);

    expect(events.map((e) => e.type)).toEqual(['a', 'complete']);
  });

  it('emits a trailing frame with no terminating blank line', async () => {
    const events = await collect(['data: {"type":"complete"}']);
    expect(events).toHaveLength(1);
    expect(events[0].type).toBe('complete');
  });

  it('handles multi-byte characters split across chunks', async () => {
    const encoder = new TextEncoder();
    const full = encoder.encode('data: {"type":"t","track":{"artist":"Sigur Rós"}}\n\n');
    // Cut mid-way through the two-byte ó.
    const cut = full.indexOf(0xc3) + 1;

    let i = 0;
    const parts = [full.slice(0, cut), full.slice(cut)];
    const response = {
      body: {
        getReader: () => ({
          read: async () =>
            i < parts.length ? { done: false, value: parts[i++] } : { done: true, value: undefined },
          releaseLock: () => {},
        }),
      },
    };

    const events = [];
    for await (const event of readEventStream(response)) events.push(event);

    expect(events[0].track.artist).toBe('Sigur Rós');
  });

  it('skips malformed frames without ending the stream', async () => {
    jest.spyOn(console, 'warn').mockImplementation(() => {});
    const events = await collect([
      'data: not json at all\n\n',
      'data: {"type":"complete"}\n\n',
    ]);

    expect(events).toHaveLength(1);
    expect(events[0].type).toBe('complete');
    console.warn.mockRestore();
  });
});
