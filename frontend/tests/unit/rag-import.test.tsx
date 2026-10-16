// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import RagManager from '../../src/features/rag/RagManager';
import { ragApi } from '../../src/api/rag';
vi.mock('../../src/api/file', () => ({ fileApi: { listFiles: vi.fn().mockResolvedValue([{ filename: 'report.txt', file_hash: 'sha256-report' }]) } }));
vi.mock('../../src/api/rag', () => ({ ragApi: { getRagFiles: vi.fn().mockResolvedValue({ success: true, files: [] }), getRagFileStatus: vi.fn().mockResolvedValue({ success: true, statuses: {} }), buildRag: vi.fn().mockResolvedValue({ success: false, message: 'Test response' }) } }));
vi.mock('../../src/context/ProjectContext', () => ({ useProjects: () => ({ projects: [{ id: 'project-1' }], loading: false }) }));
vi.mock('../../src/context/ThemeContext', () => ({ useTheme: () => ({ isDarkMode: false }) }));
vi.mock('../../src/context/LanguageContext', () => ({ useLanguage: () => ({ currentLanguage: 'en-US', t: (key: string) => key }) }));
afterEach(cleanup);
it('displays the filename but submits the persisted file hash', async () => {
  render(<MemoryRouter><RagManager /></MemoryRouter>);
  const label = await screen.findByText('report.txt');
  fireEvent.click(label.parentElement!.querySelector('input')!);
  fireEvent.click(screen.getByRole('button', { name: 'importSelectedFiles' }));
  await waitFor(() => expect(ragApi.buildRag).toHaveBeenCalledWith('project-1', ['sha256-report']));
});
