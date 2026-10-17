// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { afterEach, expect, it } from 'vitest';
import ProjectEntry from '../../src/features/project/ProjectEntry';
import { projectDestination } from '../../src/features/project/projectNavigation';
afterEach(cleanup);
function Location() { const location=useLocation();return <div>{location.pathname}{location.search}</div>; }
it('asks for a project without mounting a tool or choosing the first project',()=>{
 render(<MemoryRouter initialEntries={['/app/chat?conversation=thread-1']}><Routes><Route path="/app/chat" element={<ProjectEntry section="chat"/>}/><Route path="/app/projects" element={<Location/>}/></Routes></MemoryRouter>);
 expect(screen.getByText('/app/projects?conversation=thread-1&section=chat')).toBeTruthy();
});
it('continues the requested tool only after an explicit project choice',()=>{
 expect(projectDestination('chosen',new URLSearchParams('section=chat&conversation=thread-1'))).toBe('/project/chosen/chat?conversation=thread-1');
 expect(projectDestination('chosen',new URLSearchParams('section=documents&file=report&conversation=wrong'))).toBe('/project/chosen/documents?file=report');
});
it('defaults to overview and rejects arbitrary destinations',()=>{
 expect(projectDestination('chosen',new URLSearchParams('section=https://example.com'))).toBe('/project/chosen/dashboard');
 expect(projectDestination('chosen',new URLSearchParams())).toBe('/project/chosen/dashboard');
});
