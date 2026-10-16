// @vitest-environment jsdom
import { expect, it } from 'vitest';
import { apiClient } from '../../src/api/client';
it('does not overwrite the knowledge query timeout with the generic 15 seconds', async () => {
  await apiClient.post('/api/lightrag/rag/search', {}, {
    timeout: 120000,
    adapter: async config => {
      expect(config.timeout).toBe(120000);
      return { config, status: 200, statusText: 'OK', headers: {}, data: { success: true } };
    },
  });
});
