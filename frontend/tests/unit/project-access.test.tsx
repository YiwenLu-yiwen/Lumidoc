// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { AuthGuard } from '../../src/context/AuthGuard';
import { projectApi } from '../../src/api/project';
vi.mock('../../src/api/project', () => ({ projectApi: { getProject: vi.fn().mockResolvedValue({ id: '2011d7a1-fa0c-4805-b784-4636dbe94906' }) } }));
const auth = { isAuthenticated: true, hasProjectAccess: () => true, updateUserProjectAccess: vi.fn(), user: { id: '2' } };
vi.mock('../../src/context/AuthContext', () => ({ useAuth: () => auth }));
vi.mock('../../src/utils/toast', () => ({ customToast: { error: vi.fn() } }));
afterEach(() => { cleanup(); sessionStorage.clear(); localStorage.clear(); vi.clearAllMocks(); });

describe('project access', () => {
  it('opens a UUID project using the route rather than stale navigation state', async () => {
    const id = '2011d7a1-fa0c-4805-b784-4636dbe94906';
    sessionStorage.setItem('navigating_to_project', 'old-project');
    render(<MemoryRouter initialEntries={[`/project/${id}`]}><Routes>
      <Route path="/project/:projectId" element={<AuthGuard projectAccess><h1>Project content</h1></AuthGuard>} />
      <Route path="/" element={<h1>Home</h1>} />
    </Routes></MemoryRouter>);
    expect(await screen.findByText('Project content')).toBeTruthy();
    expect(projectApi.getProject).toHaveBeenCalledWith(id);
  });
});
