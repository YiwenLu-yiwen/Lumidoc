import { afterEach, expect, it, vi } from 'vitest';
import { streamRagQuery } from '../../src/api/ragStream';

afterEach(() => vi.unstubAllGlobals());
it('delivers split UTF-8 events before the response ends', async () => {
  vi.stubGlobal('localStorage', { getItem: () => 'test-token' });
  let controller!: ReadableStreamDefaultController<Uint8Array>;
  const body = new ReadableStream<Uint8Array>({ start(value) { controller = value; } });
  const fetcher = vi.fn().mockResolvedValue(new Response(body));
  vi.stubGlobal('fetch', fetcher);
  const events = vi.fn();
  const pending = streamRagQuery('project', 'question', events, new AbortController().signal);
  const bytes = new TextEncoder().encode('data: {"content":"你好"}\n\n');
  controller.enqueue(bytes.slice(0, 20));
  controller.enqueue(bytes.slice(20));
  await vi.waitFor(() => expect(events).toHaveBeenCalledWith({ content: '你好' }));
  controller.enqueue(new TextEncoder().encode('data: {"done":true}\n\n'));
  controller.close();
  expect(await pending).toBe('你好');
  expect(fetcher.mock.calls[0][1].headers.Authorization).toBe('Bearer test-token');
});
it.each(['data: {"error":"unavailable"}\n\n', 'data: {"content":"partial"}\n\n'])('rejects failed or truncated streams', async text => {
  vi.stubGlobal('localStorage', { getItem: () => 'test-token' });
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(text)));
  await expect(streamRagQuery('p', 'q', vi.fn(), new AbortController().signal)).rejects.toThrow();
});
