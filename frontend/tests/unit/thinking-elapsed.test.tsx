// @vitest-environment jsdom
import {act,cleanup,render,screen} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import {ThinkingElapsed} from '../../src/features/chat/ThinkingElapsed';
afterEach(()=>{cleanup();vi.useRealTimers();});
it('counts real elapsed seconds, freezes on completion and cleans up its timer',()=>{
 vi.useFakeTimers();vi.setSystemTime(10000);
 const view=render(<ThinkingElapsed startedAt={10000} language="en-US"/>);
 expect(screen.getByLabelText('Thinking time').textContent).toBe('0s');
 act(()=>vi.advanceTimersByTime(4000));expect(screen.getByLabelText('Thinking time').textContent).toBe('4s');
 view.rerender(<ThinkingElapsed startedAt={10000} finishedAt={14200} language="en-US"/>);
 act(()=>vi.advanceTimersByTime(5000));expect(screen.getByLabelText('Thinking time').textContent).toBe('4s');
 expect(vi.getTimerCount()).toBe(0);
});
it('does not invent timings for non-thinking or historical messages',()=>{
 const view=render(<ThinkingElapsed language="en-US"/>);expect(view.container.textContent).toBe('');
});
