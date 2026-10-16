export interface RagStreamEvent {
  content?: string;
  stage?: string;
  error?: string;
  done?: boolean;
  timings?: { retrieval_ms: number; first_token_ms: number; total_ms: number };
}

export async function streamRagQuery(
  projectId: string,
  query: string,
  onEvent: (event: RagStreamEvent) => void,
  signal: AbortSignal,
): Promise<string> {
  const gateway = import.meta.env.VITE_API_GATEWAY_URL || 'http://localhost:8888';
  const response = await fetch(`${gateway}/api/lightrag/rag/search/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${localStorage.getItem('lumidoc_token') || ''}`,
    },
    body: JSON.stringify({ project_id: projectId, query, mode: 'hybrid' }),
    signal,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(typeof body?.detail === 'string' ? body.detail : `Query failed (${response.status})`);
  }
  if (!response.body) throw new Error('Streaming is unavailable');
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let answer = '';
  let complete = false;
  const consume = (line: string) => {
    if (!line.startsWith('data:')) return;
    const event: RagStreamEvent = JSON.parse(line.slice(5).trim());
    if (event.error) throw new Error(event.error);
    if (event.content) answer += event.content;
    if (event.done) complete = true;
    onEvent(event);
  };
  try {
    while (!complete) {
      const { done, value } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';
      for (const line of lines) consume(line.trimEnd());
      if (done) {
        if (buffer.trim()) consume(buffer);
        break;
      }
    }
    if (!complete) throw new Error('The answer stream was interrupted');
    return answer;
  } finally {
    await reader.cancel().catch(() => undefined);
    reader.releaseLock();
  }
}
