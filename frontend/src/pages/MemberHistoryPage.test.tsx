import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { MemberHistoryPage } from './MemberHistoryPage';

const { listMemberHistory } = vi.hoisted(() => ({ listMemberHistory: vi.fn() }));
vi.mock('@/api/memberFeedback', () => ({ listMemberHistory }));
vi.mock('@/app/TimeSettingsContext', () => ({
  useTimeSettings: () => ({ formatTimestamp: (value: string) => `portal time ${value}` }),
}));

afterEach(() => { cleanup(); vi.resetAllMocks(); });

function DirectoryLocation() {
  const location = useLocation();
  return <p>Provider directory {location.search}</p>;
}

describe('MemberHistoryPage', () => {
  it('restores only supported saved search filters and renders configured timestamps', async () => {
    const user = userEvent.setup();
    listMemberHistory.mockResolvedValue({
      data: [{
        id: 'h1', event_key: 'search:one', type: 'search', provider_id: null,
        provider_name: null, provider_available: null,
        filters: { name: 'field vet', region: 'North Coast', unsupported: 'not-restored' },
        occurred_at: '2026-04-05T10:00:00Z',
      }],
      meta: { page: 1, page_size: 10, total: 1, total_pages: 1 },
    });
    render(<MemoryRouter initialEntries={['/history']}><Routes>
      <Route path="/history" element={<MemberHistoryPage />} />
      <Route path="/providers" element={<DirectoryLocation />} />
    </Routes></MemoryRouter>);
    expect(await screen.findByText('Provider search')).toBeTruthy();
    expect(screen.getByText('portal time 2026-04-05T10:00:00Z')).toBeTruthy();
    await user.click(screen.getByRole('button', { name: /Restore search/ }));
    const directory = await screen.findByText(/Provider directory/);
    expect(directory.textContent).toContain('name=field+vet');
    expect(directory.textContent).toContain('region=North+Coast');
    expect(directory.textContent).not.toContain('unsupported');
  });

  it('handles unavailable provider history without attempting to open its profile', async () => {
    const user = userEvent.setup();
    listMemberHistory.mockResolvedValue({
      data: [{
        id: 'h2', event_key: 'provider:one', type: 'provider', provider_id: 'gone',
        provider_name: 'Unavailable provider', provider_available: false,
        filters: null, occurred_at: '2026-04-06T10:00:00Z',
      }],
      meta: { page: 1, page_size: 10, total: 1, total_pages: 1 },
    });
    render(<MemoryRouter initialEntries={['/history']}><Routes>
      <Route path="/history" element={<MemberHistoryPage />} />
      <Route path="/providers" element={<p>Provider directory</p>} />
    </Routes></MemoryRouter>);
    expect(await screen.findByText('Unavailable provider')).toBeTruthy();
    expect(screen.getByText('This provider profile is no longer available.')).toBeTruthy();
    await user.click(screen.getByText('Unavailable'));
    expect(screen.getByText('Unavailable provider')).toBeTruthy();
  });
});