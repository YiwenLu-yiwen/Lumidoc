import { afterEach, expect, it, vi } from 'vitest';
import { apiClient } from '../../src/api/client';
import { ragApi } from '../../src/api/rag';
vi.mock('../../src/api/client', () => ({ apiClient: { post: vi.fn() } }));
afterEach(() => vi.clearAllMocks());
it('uses one query endpoint with a timeout appropriate for local generation', async () => {
  vi.mocked(apiClient.post).mockResolvedValue({ data: { success: true, result: 'Answer' } });
  expect(await ragApi.queryRag('project', 'Question')).toEqual({ success: true, result: 'Answer' });
  expect(apiClient.post).toHaveBeenCalledExactlyOnceWith('/api/lightrag/rag/search', { query: 'Question', project_id: 'project', mode: 'hybrid', top_k: 5 }, { timeout: 120000 });
});
it('preserves the real service error without retrying nonexistent routes', async () => {
  vi.mocked(apiClient.post).mockRejectedValue({ isAxiosError: true, response: { status: 503, data: { detail: '模型连接失败' } } });
  const result = await ragApi.queryRag('project', 'Question');
  expect(apiClient.post).toHaveBeenCalledTimes(1);
  expect(result.success).toBe(false);
  expect(result.result).toContain('模型连接失败');
});
