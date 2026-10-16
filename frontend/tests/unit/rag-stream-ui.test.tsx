// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import RagManager from '../../src/features/rag/RagManager';
import { streamRagQuery, type RagStreamEvent } from '../../src/api/ragStream';
vi.mock('../../src/api/ragStream', () => ({ streamRagQuery: vi.fn() }));
vi.mock('../../src/api/file', () => ({ fileApi: { listFiles: vi.fn().mockResolvedValue([]) } }));
vi.mock('../../src/api/rag', () => ({ ragApi: { getRagFiles: vi.fn().mockResolvedValue({success:true,files:[]}), getRagFileStatus: vi.fn().mockResolvedValue({success:true,statuses:{}}) } }));
vi.mock('../../src/context/ProjectContext', () => ({ useProjects: () => ({projects:[{id:'project-1'}],loading:false}) }));
vi.mock('../../src/context/ThemeContext', () => ({ useTheme: () => ({isDarkMode:false}) }));
vi.mock('../../src/context/LanguageContext', () => ({useLanguage: () => ({currentLanguage:'en-US',t:(key:string)=>key})}));
afterEach(cleanup);
it('shows partial content immediately and lets the user stop the request', async () => {
  let emit!: (event:RagStreamEvent)=>void;
  let activeSignal!: AbortSignal;
  vi.mocked(streamRagQuery).mockImplementation((_project,_query,onEvent,signal)=>{
    emit=onEvent;
    activeSignal=signal;
    return new Promise((_resolve,reject)=>signal.addEventListener('abort',()=>reject(new DOMException('Stopped','AbortError'))));
  });
  render(<MemoryRouter><RagManager /></MemoryRouter>);
  fireEvent.change(screen.getByPlaceholderText('queryPlaceholder'),{target:{value:'Find the inspection time'}});
  fireEvent.click(screen.getByRole('button',{name:'query',exact:true}));
  await waitFor(()=>expect(streamRagQuery).toHaveBeenCalled());
  act(()=>emit({content:'Inspection is '}));
  expect(screen.getByText('Inspection is')).toBeTruthy();
  fireEvent.click(screen.getByRole('button',{name:'Stop',exact:true}));
  expect(activeSignal.aborted).toBe(true);
  await waitFor(()=>expect(screen.getByRole('button',{name:'query',exact:true})).toBeTruthy());
});
