// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import ChatLayout from '../../src/features/chat/ChatLayout';
vi.mock('../../src/context/ProjectContext', () => ({ useProjects: () => ({ projects: [{ id: 'project-1' }] }) }));
vi.mock('../../src/context/ThemeContext', () => ({ useTheme: () => ({ isDarkMode: false }) }));
vi.mock('../../src/context/LanguageContext', () => ({ useLanguage: () => ({ currentLanguage: 'en-US', t: (key: string) => key }) }));
vi.mock('../../src/hooks/useModel', () => ({ useSelectedModel: () => ({ selectedModel: { id: 'qwen3:1.7b', supportsThinking: true } }) }));
vi.mock('../../src/features/chat/components/MigrationButton', () => ({ default: () => null }));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); localStorage.clear(); });

it('does not replace a new reply with a late empty history response', async () => {
  let finishHistory!: (response: Response) => void;
  const history = new Promise<Response>(resolve => { finishHistory = resolve; });
  vi.stubGlobal('fetch', vi.fn((url: string) => {
    if (url.includes('/history/')) return history;
    if (url.endsWith('/stream')) return Promise.resolve(new Response('data: {"content":"Verified reply"}\n\ndata: {"done":true}\n\n'));
    return Promise.resolve(new Response('{}'));
  }));
  Element.prototype.scrollIntoView = vi.fn();
  localStorage.setItem('lumidoc_user', JSON.stringify({ id: 'test-user' }));
  render(<MemoryRouter><ChatLayout /></MemoryRouter>);
  const input = screen.getByPlaceholderText('Enter your question, press Enter to send...');
  fireEvent.change(input, { target: { value: 'Hello' } });
  fireEvent.submit(input.closest('form')!);
  expect(await screen.findByText('Verified reply')).toBeTruthy();
  await act(async () => { finishHistory(new Response('[]')); await history; });
  expect(screen.getByText('Verified reply')).toBeTruthy();
});

it('loads a background reply after returning while generation is pending', async () => {
  let pending = true;
  vi.stubGlobal('fetch', vi.fn((url: string) => {
    if (url.includes('/pending/')) return Promise.resolve(new Response(JSON.stringify({ pending })));
    if (url.includes('/history/')) return Promise.resolve(new Response(JSON.stringify(pending
      ? [{ role: 'user', content: '职位是什么？' }]
      : [{ role: 'user', content: '职位是什么？' }, { role: 'assistant', content: '软件工程师' }])));
    return Promise.resolve(new Response('{}'));
  }));
  Element.prototype.scrollIntoView = vi.fn();
  render(<MemoryRouter><ChatLayout /></MemoryRouter>);
  expect(await screen.findByText('Reply continues in the background')).toBeTruthy();
  pending = false;
  expect(await screen.findByText('软件工程师', {}, { timeout: 5000 })).toBeTruthy();
});

it('restores the selected conversation when returning from another page', async () => {
  const fetchMock = vi.fn((url: string) => Promise.resolve(new Response(url.includes('/history/') ? '[]' : '{}')));
  vi.stubGlobal('fetch', fetchMock);
  const first = render(<MemoryRouter initialEntries={['/chat?conversation=conversation-a']}><ChatLayout /></MemoryRouter>);
  await act(async () => {});
  first.unmount();
  fetchMock.mockClear();
  render(<MemoryRouter initialEntries={['/chat']}><ChatLayout /></MemoryRouter>);
  await act(async () => {});
  expect(fetchMock.mock.calls.some(([url]) => url.includes('/history/') && url.includes('session_id=conversation-a'))).toBe(true);
  sessionStorage.clear();
});

it('stops backend generation, retains the partial reply and allows another question', async () => {
  let controller!: ReadableStreamDefaultController<Uint8Array>;
  let stopped = false;
  const encoder = new TextEncoder();
  const fetchMock = vi.fn((url: string) => {
    if (url.includes('/history/')) return Promise.resolve(new Response(JSON.stringify(stopped ? [
      { id: 'u', role: 'user', content: 'Write a long answer' },
      { id: 'a', role: 'assistant', content: 'Partial answer' },
    ] : [])));
    if (url.endsWith('/stream')) return Promise.resolve(new Response(new ReadableStream({ start(c) {
      controller = c;
      c.enqueue(encoder.encode('data: {"content":"Partial answer"}\n\n'));
    }})));
    if (url.includes('/stop/')) {
      stopped = true;
      controller.enqueue(encoder.encode('data: {"stopped":true}\n\ndata: {"done":true}\n\n'));
      controller.close();
      return Promise.resolve(new Response('{"success":true,"stopped":1}'));
    }
    return Promise.resolve(new Response('{}'));
  });
  vi.stubGlobal('fetch', fetchMock);
  render(<MemoryRouter><ChatLayout /></MemoryRouter>);
  fireEvent.click(screen.getByRole('switch', { name: /Thinking mode/ }));
  const input = screen.getByPlaceholderText('Enter your question, press Enter to send...');
  fireEvent.change(input, { target: { value: 'Write a long answer' } });
  fireEvent.submit(input.closest('form')!);
  await screen.findByText('Partial answer');
  fireEvent.click(await screen.findByRole('button', { name: 'Stop generating' }));
  await screen.findByRole('button', { name: 'Send message' });
  expect(input).toHaveProperty('disabled', false);
  expect(screen.getByLabelText('Thinking time').textContent).toMatch(/^[0-9]+s$/);
  expect(screen.getAllByText('Partial answer')).toHaveLength(1);
  expect(fetchMock.mock.calls.some(([url]) => url.includes('/stop/project-1') && url.includes('session_id=legacy'))).toBe(true);
  expect(screen.queryByRole('button', { name: 'Unlock Status' })).toBeNull();
});

it('clears the active conversation when it is deleted from the sidebar', async () => {
  vi.stubGlobal('fetch', vi.fn((url: string) => Promise.resolve(new Response(
    url.includes('/history/') && url.includes('session_id=delete-me')
      ? '[{"id":"u1","role":"user","content":"Selected conversation"}]' : url.includes('/history/') ? '[]' : '{}'
  ))));
  render(<MemoryRouter initialEntries={['/chat?conversation=delete-me']}><ChatLayout /></MemoryRouter>);
  await screen.findByText('Selected conversation');
  await act(async () => { window.dispatchEvent(new CustomEvent('conversation-deleted', { detail: { projectId: 'project-1', conversationId: 'delete-me' } })); });
  expect(screen.queryByText('Selected conversation')).toBeNull();
});

it('keeps history and deletion controls in the sidebar, without a chat toolbar', () => {
  vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(new Response('[]'))));
  render(<MemoryRouter><ChatLayout /></MemoryRouter>);
  expect(screen.queryByRole('button', {name: 'Delete current conversation'})).toBeNull();
  expect(screen.queryByTitle('View History Messages')).toBeNull();
});

it('shows native thinking before the answer and sends an explicit mode', async () => {
  let controller!: ReadableStreamDefaultController<Uint8Array>;
  let payload: { think?: boolean } = {};
  const encoder = new TextEncoder();
  vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => {
    if (url.includes('/history/')) return Promise.resolve(new Response('[]'));
    if (url.endsWith('/stream')) {
      payload = JSON.parse(String(init?.body));
      return Promise.resolve(new Response(new ReadableStream({ start(c) {
        controller = c;
        c.enqueue(encoder.encode('data: {"thinking":"Native reasoning"}\n\n'));
      }})));
    }
    return Promise.resolve(new Response('{}'));
  }));
  render(<MemoryRouter><ChatLayout /></MemoryRouter>);
  const toggle = screen.getByRole('switch', { name: /Thinking mode/ });
  expect(toggle.getAttribute('aria-checked')).toBe('false');
  fireEvent.click(toggle);
  const input = screen.getByPlaceholderText('Enter your question, press Enter to send...');
  fireEvent.change(input, { target: { value: 'Question' } });
  fireEvent.submit(input.closest('form')!);
  await screen.findByText('Native reasoning');
  expect(payload.think).toBe(true);
  expect(document.querySelector('.prose')?.textContent).toBe('');
  await act(async () => {
    controller.enqueue(encoder.encode('data: {"content":"Final answer"}\n\ndata: {"done":true}\n\n'));
    controller.close();
  });
  expect(await screen.findByText('Final answer')).toBeTruthy();
  expect(document.querySelector('.prose')?.textContent).toBe('Final answer');
});

it('loads earlier messages by scrolling without restoring the history toolbar', async()=>{
 const recent=Array.from({length:50},(_,i)=>({id:`recent-${i}`,role:'user',content:`Recent ${i}`}));
 const fetchMock=vi.fn((url:string)=>Promise.resolve(new Response(JSON.stringify(url.includes('/history/') ? (url.includes('offset=50') ? [{id:'older',role:'user',content:'Earlier message'}] : recent) : {}))));
 vi.stubGlobal('fetch',fetchMock);
 render(<MemoryRouter><ChatLayout/></MemoryRouter>);
 await screen.findByText('Recent 49');
 const messages=screen.getByLabelText('Chat messages');
 Object.defineProperty(messages,'scrollHeight',{configurable:true,value:1000});
 Object.defineProperty(messages,'clientHeight',{configurable:true,value:200});
 messages.scrollTop=0;fireEvent.scroll(messages);
 await screen.findByText('Earlier message');
 await waitFor(()=>expect(fetchMock.mock.calls.filter(([url])=>url.includes('offset=50'))).toHaveLength(1));
 expect(screen.getByText('Recent 49')).toBeTruthy();
});

it('recovers a gateway-closed stream and reloads its completed reply without refreshing', async () => {
  let accepted = false;
  let completed = false;
  vi.stubGlobal('fetch', vi.fn((url: string) => {
    if (url.includes('/pending/')) return Promise.resolve(new Response(JSON.stringify({ pending: accepted && !completed })));
    if (url.includes('/history/')) return Promise.resolve(new Response(JSON.stringify(completed ? [
      { id: 'u', role: 'user', content: 'Recover this reply' },
      { id: 'a', role: 'assistant', content: 'Recovered final answer' },
    ] : [])));
    if (url.endsWith('/stream')) {
      accepted = true;
      return Promise.resolve(new Response('data: {"content":"Interrupted partial answer"}\n\ndata: {"error":"Processing error, please retry"}\n\n'));
    }
    return Promise.resolve(new Response('{}'));
  }));
  Element.prototype.scrollIntoView = vi.fn();
  render(<MemoryRouter><ChatLayout /></MemoryRouter>);
  const input = screen.getByPlaceholderText('Enter your question, press Enter to send...');
  fireEvent.change(input, { target: { value: 'Recover this reply' } });
  fireEvent.submit(input.closest('form')!);
  await screen.findByText('Reply continues in the background');
  expect(screen.queryByText(/Processing error/)).toBeNull();
  completed = true;
  await screen.findByText('Recovered final answer', {}, { timeout: 5000 });
  expect(screen.queryByText('Interrupted partial answer')).toBeNull();
  expect(screen.getAllByText('Recovered final answer')).toHaveLength(1);
  expect(input).toHaveProperty('disabled', false);
});
