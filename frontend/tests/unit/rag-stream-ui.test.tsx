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

it('resumes import polling after mounting and stops polling on unmount', async () => {
  const { ragApi } = await import('../../src/api/rag');
  vi.useFakeTimers();
  vi.mocked(ragApi.getRagFileStatus).mockResolvedValueOnce({success:true,statuses:{file:{status:'processing',file_name:'report.txt',stage:'indexing'}}});
  vi.mocked(ragApi.getRagFileStatus).mockResolvedValue({success:true,statuses:{file:{status:'processed',file_name:'report.txt'}}});
  const view = render(<MemoryRouter><RagManager /></MemoryRouter>);
  await act(async () => { await vi.advanceTimersByTimeAsync(0); });
  expect(screen.getByText('Processing', {exact:false})).toBeTruthy();
  await act(async () => { await vi.advanceTimersByTimeAsync(3000); });
  expect(screen.getByText('Processed', {exact:true})).toBeTruthy();
  view.unmount();
  const count = vi.mocked(ragApi.getRagFileStatus).mock.calls.length;
  await act(async () => { await vi.advanceTimersByTimeAsync(6000); });
  expect(vi.mocked(ragApi.getRagFileStatus).mock.calls.length).toBe(count);
  vi.useRealTimers();
});

it('batch deletes selected documents and keeps failed items selected', async () => {
  const { ragApi } = await import('../../src/api/rag');
  vi.mocked(ragApi.getRagFileStatus).mockResolvedValue({success:true,statuses:{
    a:{status:'processed',file_name:'a.txt'},b:{status:'processed',file_name:'b.txt'},
  }});
  ragApi.deleteRagFiles = vi.fn().mockResolvedValue({success:false,duration_seconds:1.25,results:[
    {file_id:'a',success:true,message:'Deleted',duration_seconds:.5},
    {file_id:'b',success:false,message:'Retry required',duration_seconds:.75},
  ]});
  vi.spyOn(window,'confirm').mockReturnValue(true);
  render(<MemoryRouter><RagManager /></MemoryRouter>);
  await screen.findByRole('checkbox',{name:'Select for deletion a.txt'});
  fireEvent.click(screen.getByRole('button',{name:'Select all deletable documents'}));
  fireEvent.click(screen.getByRole('button',{name:'Delete selected (2)'}));
  await screen.findByText('Deleted 1, failed 1, 1.25 seconds');
  expect(ragApi.deleteRagFiles).toHaveBeenCalledWith('project-1',['a','b']);
  expect(screen.getByRole('checkbox',{name:'Select for deletion a.txt'})).toHaveProperty('checked',false);
  expect(screen.getByRole('checkbox',{name:'Select for deletion b.txt'})).toHaveProperty('checked',true);
  vi.restoreAllMocks();
});
