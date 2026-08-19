import { afterEach, describe, expect, it, vi } from 'vitest';

import { apiClient } from '../../src/api/client';
import { getAvailableModels } from '../../src/api/modelService';


describe('getAvailableModels', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('does not present invented models when the backend is unavailable', async () => {
    vi.spyOn(apiClient, 'get').mockRejectedValue(new Error('backend offline'));

    await expect(getAvailableModels()).rejects.toThrow('获取模型列表失败');
  });
});
