import { describe, expect, it, vi } from 'vitest';
import { apiClient } from '../../src/api/client';
import { fileApi } from '../../src/api/file';
vi.mock('../../src/api/client', () => ({ apiClient: { get: vi.fn() } }));

describe('fileApi.listFiles', () => {
  it('preserves names and types from the file-service response schema', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: [{ file_hash: 'sha256', name: 'report.pdf', type: 'application/pdf', path: 'uploads/project/sha256.pdf', size: 16, status: 'completed' }] });
    const [file] = await fileApi.listFiles('project');
    expect(file.filename).toBe('report.pdf');
    expect(file.display_name).toBe('report.pdf');
    expect(file.content_type).toBe('application/pdf');
    expect(file.file_hash).toBe('sha256');
  });
});
