// @vitest-environment jsdom
import {cleanup, render, screen, fireEvent} from '@testing-library/react';
import {afterEach, expect, it, vi} from 'vitest';
import AdminPage from '../../src/features/admin/AdminPage';
import {apiClient} from '../../src/api/client';
const identity=vi.hoisted(()=>({user:{id:'1',role:'user'}}));
vi.mock('../../src/context/AuthContext',()=>({useAuth:()=>identity}));
vi.mock('../../src/context/LanguageContext',()=>({useLanguage:()=>({currentLanguage:'en-US'})}));
vi.mock('../../src/api/client',()=>({apiClient:{get:vi.fn(),patch:vi.fn()}}));
afterEach(()=>{cleanup();vi.clearAllMocks();identity.user.role='user';});
it('does not request privileged data for an ordinary user',()=>{render(<AdminPage/>);expect(screen.getByRole('alert').textContent).toContain('Administrator access required');expect(apiClient.get).not.toHaveBeenCalled();});
it('shows service failure honestly and allows retry',async()=>{
 identity.user.role='admin';vi.mocked(apiClient.get).mockRejectedValueOnce(new Error('offline')).mockResolvedValueOnce({data:{services:[],models:null,resources:{cpu_percent:0,memory_percent:0},checked_at:'2026-10-18T00:00:00Z'}});
 render(<AdminPage/>);await screen.findByRole('alert');fireEvent.click(screen.getByRole('button',{name:'Refresh'}));await screen.findByText('Runtime information unavailable');
});
