// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { DocumentAnalysis } from '../../src/components/document/DocumentAnalysis';
import { fileApi, type FileInfo } from '../../src/api/file';

vi.mock('../../src/api/file', () => ({ fileApi: { listFiles: vi.fn(), uploadFiles: vi.fn(), getFileBlob: vi.fn(), getFileContent: vi.fn(), deleteFile: vi.fn() } }));
vi.mock('../../src/context/ProjectContext', () => ({ useProjects: () => ({ projects: [{ id: 'project-1', name: 'Project' }], loading: false }) }));
vi.mock('../../src/context/ThemeContext', () => ({ useTheme: () => ({ isDarkMode: false }) }));
vi.mock('../../src/context/LanguageContext', () => ({ useLanguage: () => ({ currentLanguage: 'en-US', t: (key: string) => ({ noDocuments: 'No documents yet', uploadFirstDocument: 'Upload a document to start analysis.' } as Record<string, string>)[key] || key }) }));

const storedFile: FileInfo = { file_id: '1', file_hash: 'hash-1', filename: 'saved.txt', display_name: 'saved.txt', path: '', size: 8, file_type: 'text/plain', content_type: 'text/plain', created_at: '2026-10-08T00:00:00Z', updated_at: '', metadata: '', status: 'completed' };
const mount = () => render(<MemoryRouter><DocumentAnalysis /></MemoryRouter>);
afterEach(cleanup);
beforeEach(() => { vi.clearAllMocks(); vi.mocked(fileApi.listFiles).mockResolvedValue([]); });

describe('DocumentAnalysis', () => {
  it('loads the server file list again after remounting', async () => {
    vi.mocked(fileApi.listFiles).mockResolvedValue([storedFile]);
    const first = mount();
    expect(await screen.findByText('saved.txt')).toBeTruthy();
    first.unmount();
    mount();
    expect(await screen.findByText('saved.txt')).toBeTruthy();
    expect(fileApi.listFiles).toHaveBeenCalledWith('project-1');
  });

  it('uploads to the selected project and reloads persisted records', async () => {
    vi.mocked(fileApi.uploadFiles).mockImplementation(async () => {
      vi.mocked(fileApi.listFiles).mockResolvedValue([storedFile]);
      return { success: true, files: [{ success: true, file_id: '1', file_path: '', task_id: '', message: '' }] };
    });
    const { container } = mount();
    await screen.findByText('No documents yet');
    const file = new File(['document'], 'saved.txt', { type: 'text/plain' });
    fireEvent.change(container.querySelector('input[type="file"]')!, { target: { files: [file] } });
    await waitFor(() => expect(fileApi.uploadFiles).toHaveBeenCalledWith('project-1', [file], expect.any(Function)));
    expect(await screen.findByText('saved.txt')).toBeTruthy();
  });

  it('does not report completion when the server rejects an upload', async () => {
    vi.mocked(fileApi.uploadFiles).mockResolvedValue({ success: false, files: [{ success: false, message: 'Storage unavailable', file_path: '', task_id: '' }] });
    const { container } = mount();
    await screen.findByText('No documents yet');
    fireEvent.change(container.querySelector('input[type="file"]')!, { target: { files: [new File(['x'], 'failed.txt')] } });
    expect(await screen.findByRole('alert')).toHaveProperty('textContent', 'Storage unavailable');
    expect(screen.queryByText('failed.txt')).toBeNull();
  });
});


it('previews OCR output for scanned PDFs rather than the original binary', async () => {
  vi.mocked(fileApi.listFiles).mockResolvedValue([{ ...storedFile, filename: 'scan.pdf', display_name: 'scan.pdf', file_type: 'application/pdf' }]);
  vi.mocked(fileApi.getFileContent).mockResolvedValue('OCR result: Software Engineer');
  mount();
  fireEvent.click(await screen.findByText('scan.pdf'));
  fireEvent.click(screen.getByRole('button', { name: 'Preview', exact: true }));
  expect(await screen.findByText('OCR result: Software Engineer')).toBeTruthy();
  expect(fileApi.getFileContent).toHaveBeenCalledWith('project-1', 'hash-1');
  expect(fileApi.getFileBlob).not.toHaveBeenCalled();
});

it('downloads the same processed content with a Markdown extension', async () => {
  vi.mocked(fileApi.listFiles).mockResolvedValue([{ ...storedFile, filename: 'scan.pdf', display_name: 'scan.pdf', file_type: 'application/pdf' }]);
  vi.mocked(fileApi.getFileContent).mockResolvedValue('Recognized text');
  const createURL = vi.fn<(blob: Blob) => string>(() => 'blob:processed');
  URL.createObjectURL = createURL;
  URL.revokeObjectURL = vi.fn();
  let filename = '';
  const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) { filename = this.download; });
  mount();
  fireEvent.click(await screen.findByText('scan.pdf'));
  fireEvent.click(screen.getByRole('button', { name: 'Download', exact: true }));
  await waitFor(() => expect(filename).toBe('scan.processed.md'));
  const blob = createURL.mock.calls[0][0] as Blob;
  expect(blob.type).toBe('text/markdown;charset=utf-8');
  expect(fileApi.getFileBlob).not.toHaveBeenCalled();
  click.mockRestore();
});


it('deletes a confirmed document by hash and reloads the list', async () => {
  vi.mocked(fileApi.listFiles).mockResolvedValue([storedFile]);
  vi.mocked(fileApi.deleteFile).mockImplementation(async () => {
    vi.mocked(fileApi.listFiles).mockResolvedValue([]);
    return { success: true, message: 'Deleted' };
  });
  const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true);
  mount();
  fireEvent.click(await screen.findByRole('button', { name: 'Delete saved.txt' }));
  await screen.findByText('No documents yet');
  expect(fileApi.deleteFile).toHaveBeenCalledWith('project-1', 'hash-1');
  confirm.mockRestore();
});

it('keeps a document when deletion is cancelled or rejected', async () => {
  vi.mocked(fileApi.listFiles).mockResolvedValue([storedFile]);
  const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
  mount();
  const button = await screen.findByRole('button', { name: 'Delete saved.txt' });
  fireEvent.click(button);
  expect(fileApi.deleteFile).not.toHaveBeenCalled();
  confirm.mockReturnValue(true);
  vi.mocked(fileApi.deleteFile).mockResolvedValue({ success: false, message: 'Deletion failed' });
  fireEvent.click(button);
  expect(await screen.findByRole('alert')).toHaveProperty('textContent', 'Deletion failed');
  expect(screen.getByText('saved.txt')).toBeTruthy();
  confirm.mockRestore();
});
