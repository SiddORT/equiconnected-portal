import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import * as invitationsApi from '@/api/invitations';
import type { Invitation } from '@/types';
import { InvitationsPage } from './InvitationsPage';

vi.mock('@/api/invitations', () => ({
  cancelInvitation: vi.fn(),
  listInvitations: vi.fn(),
  resendInvitation: vi.fn(),
  sendPortalAccess: vi.fn(),
}));

vi.mock('@/app/TimeSettingsContext', () => ({
  useTimeSettings: () => ({
    formatTimestamp: (value: string) => value,
  }),
}));

const invitation: Invitation = {
  id: 'invitation-1',
  provider_id: null,
  provider_name: 'Austin Equine Clinic',
  provider_type: 'CLINIC' as const,
  recipient_email: 'provider@example.com',
  status: 'PENDING' as const,
  expires_at: '2026-09-01T12:00:00Z',
  sent_at: '2026-08-21T12:00:00Z',
  accepted_at: null,
  completed_at: null,
  created_by: 'admin-1',
  created_at: '2026-08-21T12:00:00Z',
  updated_at: '2026-08-21T12:00:00Z',
};

function response(data: Invitation[], total = data.length) {
  return {
    data,
    meta: { page: 1, page_size: 10, total, total_pages: total === 0 ? 0 : 1 },
  };
}

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

describe('InvitationsPage', () => {
  it('hides table controls for an unfiltered empty invitation collection', async () => {
    vi.mocked(invitationsApi.listInvitations).mockResolvedValue(response([]));

    render(<MemoryRouter><InvitationsPage /></MemoryRouter>);

    expect(await screen.findByText('No invitations yet')).toBeTruthy();
    expect(screen.queryByRole('searchbox')).toBeNull();
    expect(screen.queryByRole('button', { name: /Filters/ })).toBeNull();
    expect(screen.queryByLabelText('Pagination')).toBeNull();
    expect(screen.queryByLabelText('Rows per page')).toBeNull();
    expect(screen.queryByText('Showing 0 to 0 of 0 entries')).toBeNull();
  });

  it('shows controls and pagination for a single invitation', async () => {
    vi.mocked(invitationsApi.listInvitations).mockResolvedValue(response([invitation]));
    const user = userEvent.setup();

    render(<MemoryRouter><InvitationsPage /></MemoryRouter>);

    expect(await screen.findByText('provider@example.com')).toBeTruthy();
    expect(screen.getByRole('searchbox')).toBeTruthy();
    expect(screen.getByRole('button', { name: /Filters/ })).toBeTruthy();
    expect(screen.getByLabelText('Pagination')).toBeTruthy();
    const pageSize = screen.getByLabelText('Rows per page');
    expect(pageSize).toBeTruthy();
    expect(screen.getByText('Showing 1 to 1 of 1 entries')).toBeTruthy();
    expect(screen.getByRole('button', { name: /Previous/ }).hasAttribute('disabled')).toBe(true);
    expect(screen.getByRole('button', { name: /Next/ }).hasAttribute('disabled')).toBe(true);

    await user.selectOptions(pageSize, '25');
    await waitFor(() => expect(invitationsApi.listInvitations).toHaveBeenLastCalledWith(
      expect.objectContaining({ page: 1, page_size: 25 }),
    ));
  });

  it('keeps controls available when filters return no invitations', async () => {
    vi.mocked(invitationsApi.listInvitations).mockResolvedValue(response([]));

    render(
      <MemoryRouter initialEntries={['/admin/invitations?search=missing@example.com']}>
        <InvitationsPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText('No invitations found')).toBeTruthy();
    expect(screen.getByRole('searchbox')).toBeTruthy();
    expect(screen.getByRole('button', { name: /Filters/ })).toBeTruthy();
  });

  it('renders semantic icons for the invitation actions and preserves cancel behavior', async () => {
    vi.mocked(invitationsApi.listInvitations).mockResolvedValue(response([invitation]));
    vi.mocked(invitationsApi.cancelInvitation).mockResolvedValue({ ...invitation, status: 'CANCELLED' });
    const user = userEvent.setup();

    render(<MemoryRouter><InvitationsPage /></MemoryRouter>);

    await screen.findByText('provider@example.com');
    await user.click(screen.getByRole('button', { name: 'Actions for provider@example.com' }));

    const menu = screen.getByRole('menu');
    expect(screen.getByRole('button', { name: 'Actions for provider@example.com' }).querySelector('[data-icon="more-horizontal"]')).toBeTruthy();
    expect(within(menu).getByRole('menuitem', { name: 'View' })).toBeTruthy();
    expect(within(menu).getByRole('menuitem', { name: 'Resend' })).toBeTruthy();
    const cancel = within(menu).getByRole('menuitem', { name: 'Cancel' });
    expect(cancel).toBeTruthy();
    expect(cancel.className).toContain('item--danger');
    expect(within(menu).getByRole('menuitem', { name: 'Copy Link' })).toBeTruthy();
    expect(menu.querySelectorAll('svg[data-icon]').length).toBe(4);

    await user.click(cancel);
    expect(screen.getByRole('dialog')).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'Cancel invitation' }));
    await waitFor(() => expect(invitationsApi.cancelInvitation).toHaveBeenCalledWith('invitation-1'));
  });

  it('keeps the resend action disabled with its semantic icon while the request is in progress', async () => {
    vi.mocked(invitationsApi.listInvitations).mockResolvedValue(response([invitation]));
    let resolveResend: (updated: Invitation) => void = () => {};
    vi.mocked(invitationsApi.resendInvitation).mockReturnValue(new Promise((resolve) => {
      resolveResend = resolve;
    }));
    const user = userEvent.setup();

    render(<MemoryRouter><InvitationsPage /></MemoryRouter>);

    await screen.findByText('provider@example.com');
    await user.click(screen.getByRole('button', { name: 'Actions for provider@example.com' }));
    await user.click(screen.getByRole('menuitem', { name: 'Resend' }));
    await user.click(screen.getByRole('button', { name: 'Actions for provider@example.com' }));

    const resending = screen.getByRole('menuitem', { name: 'Resending…' });
    expect(resending.hasAttribute('disabled')).toBe(true);
    expect(resending.querySelector('[data-icon="resend"]')).toBeTruthy();

    resolveResend(invitation);
  });

  it('renders the submitted-details and portal-access action icons for completed invitations', async () => {
    const completedInvitation = {
      ...invitation,
      provider_id: 'provider-1',
      status: 'COMPLETED' as const,
      portal_access_sent_at: null,
      invitation_url: null,
    };
    vi.mocked(invitationsApi.listInvitations).mockResolvedValue(
      response([completedInvitation]),
    );
    const user = userEvent.setup();

    render(<MemoryRouter><InvitationsPage /></MemoryRouter>);

    await screen.findByText('provider@example.com');
    await user.click(screen.getByRole('button', { name: 'Actions for provider@example.com' }));

    const menu = screen.getByRole('menu');
    expect(within(menu).getByRole('menuitem', { name: 'View' })).toBeTruthy();
    expect(within(menu).getByRole('menuitem', { name: 'View submitted details' })).toBeTruthy();
    expect(within(menu).getByRole('menuitem', { name: 'Send portal access' })).toBeTruthy();
    expect(menu.querySelector('[data-icon="view"]')).toBeTruthy();
    expect(menu.querySelector('[data-icon="send"]')).toBeTruthy();
  });
});