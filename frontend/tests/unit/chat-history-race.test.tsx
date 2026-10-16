// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import ChatLayout from '../../src/features/chat/ChatLayout';
vi.mock('../../src/context/ProjectContext', () => ({ useProjects: () => ({ projects: [{ id: 'project-1' }] }) }));
vi.mock('../../src/context/ThemeContext', () => ({ useTheme: () => ({ isDarkMode: false }) }));
vi.mock('../../src/context/LanguageContext', () => ({ useLanguage: () => ({ currentLanguage: 'en-US', t: (key: string) => key }) }));
vi.mock('../../src/hooks/useModel', () => ({ useSelectedModel: () => ({ selectedModel: { id: 'qwen3:1.7b' } }) }));
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
  const input = screen.getByPlaceholderText('Enter your question, press Enter to send...');
  fireEvent.change(input, { target: { value: 'Write a long answer' } });
  fireEvent.submit(input.closest('form')!);
  await screen.findByText('Partial answer');
  fireEvent.click(await screen.findByRole('button', { name: 'Stop generating' }));
  await screen.findByRole('button', { name: 'Send message' });
  expect(input).toHaveProperty('disabled', false);
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

it('deletes the current conversation and notifies the sidebar', async () => {
  const fetchMock = vi.fn((url: string) => Promise.resolve(new Response(url.includes('/history/') ? '[]' : '{"success":true}')));
  vi.stubGlobal('fetch', fetchMock);
  vi.stubGlobal('confirm', vi.fn(() => true));
  const changed = vi.fn();
  window.addEventListener('chat-updated', changed);
  render(<MemoryRouter initialEntries={['/chat?conversation=delete-me']}><ChatLayout /></MemoryRouter>);
  fireEvent.click(screen.getByRole('button', { name: 'Delete current conversation' }));
  await waitFor(() => expect(changed).toHaveBeenCalledTimes(1));
  expect(fetchMock.mock.calls.some(([url]) => url.endsWith('/chat/conversations/project-1/delete-me'))).toBe(true);
  window.removeEventListener('chat-updated', changed);
});
