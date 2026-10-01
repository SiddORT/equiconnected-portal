import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import * as providersApi from '@/api/providers';
import { ProvidersPage } from './ProvidersPage';

vi.mock('@/api/providers', () => ({
  approveProvider: vi.fn(),
  listProviders: vi.fn(),
  resendProviderApprovalEmail: vi.fn(),
  sendProviderPortalAccess: vi.fn(),
  updateProviderPublication: vi.fn(),
  updateProviderStatus: vi.fn(),
}));

vi.mock('@/app/TimeSettingsContext', () => ({
  useTimeSettings: () => ({
    settings: { timezone: 'UTC', date_format: 'month_day_year', time_format: '12_hour' },
    isLoading: false,
    error: null,
    formatTimestamp: (value: string) => value,
    formatDate: (value: string) => value,
    formatWeekday: (value: string) => value,
    refresh: vi.fn(),
  }),
}));

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

describe('ProvidersPage', () => {
  it('exposes under-review approval and sends password reset to the linked login email', async () => {
    const user = userEvent.setup();
    vi.mocked(providersApi.listProviders).mockResolvedValue({
      data: [{
        id: 'provider-reset',
        provider_type: 'CLINIC',
        name: 'Approved Clinic',
        email: 'contact@example.com',
        phone: null,
        visit_stability: 'STABLE_VISIT',
        emergency_services_available: false,
        status: 'ACTIVE',
        publication_status: 'UNPUBLISHED',
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
        thumbnail_url: null,
        average_rating: null,
        review_count: 0,
        portal_access_action: 'reset',
        portal_access_status: 'active',
        portal_login_email: 'linked-login@example.com',
      }],
      meta: { page: 1, page_size: 10, total: 1, total_pages: 1 },
    });
    vi.mocked(providersApi.sendProviderPortalAccess).mockResolvedValue({
      status: 'active',
      available: true,
      action: 'reset',
      reason: 'A password reset link can be sent.',
      recipient_email: 'linked-login@example.com',
      email_id: null,
      invitation_id: null,
      sent_at: null,
      message: 'Password reset email sent.',
      selectable_emails: [],
      can_revoke: false,
    });

    render(<MemoryRouter><ProvidersPage /></MemoryRouter>);
    await screen.findByText('Approved Clinic');
    await user.click(screen.getByRole('button', { name: 'Actions for Approved Clinic' }));
    await user.click(screen.getByRole('menuitem', { name: 'Send password reset email' }));
    expect(screen.getByRole('dialog', { name: 'Send password reset email?' })).toBeTruthy();
    expect(screen.getByText(/linked-login@example\.com/)).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'Send reset email' }));
    await waitFor(() => expect(providersApi.sendProviderPortalAccess).toHaveBeenCalledWith('provider-reset'));
    expect(await screen.findByText('Password reset email sent.')).toBeTruthy();
  });

  it('shows under-review status and approves without using the ordinary status toggle', async () => {
    const user = userEvent.setup();
    vi.mocked(providersApi.listProviders).mockResolvedValue({
      data: [{
        id: 'provider-review',
        provider_type: 'DOCTOR',
        name: 'Review Doctor',
        email: null,
        phone: null,
        visit_stability: 'NOT_STABLE_VISIT',
        emergency_services_available: false,
        status: 'UNDER_REVIEW',
        approval_available: true,
        publication_status: 'UNPUBLISHED',
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
        thumbnail_url: null,
        average_rating: null,
        review_count: 0,
      }],
      meta: { page: 1, page_size: 10, total: 1, total_pages: 1 },
    });
    vi.mocked(providersApi.approveProvider).mockResolvedValue({
      message: 'Provider approved. Approval email delivery could not be confirmed.',
      email_sent: false,
    });
    vi.mocked(providersApi.resendProviderApprovalEmail).mockResolvedValue({
      message: 'Approval email sent.',
      email_sent: true,
    });

    render(<MemoryRouter><ProvidersPage /></MemoryRouter>);
    await screen.findByText('Review Doctor');
    expect(screen.getByText('Under review')).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'Actions for Review Doctor' }));
    const menu = screen.getByRole('menu');
    expect(within(menu).getByRole('menuitem', { name: 'Approve provider' })).toBeTruthy();
    expect(within(menu).queryByRole('menuitem', { name: 'Activate' })).toBeNull();
    await user.click(within(menu).getByRole('menuitem', { name: 'Approve provider' }));
    await waitFor(() => expect(providersApi.approveProvider).toHaveBeenCalledWith('provider-review'));
    expect(await screen.findByText('Provider approved. Approval email delivery could not be confirmed.')).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'Retry approval email' }));
    await waitFor(() => expect(providersApi.resendProviderApprovalEmail).toHaveBeenCalledWith('provider-review'));
    expect(providersApi.approveProvider).toHaveBeenCalledTimes(1);
    expect(await screen.findByText('Approval email sent.')).toBeTruthy();
  });

  it('does not offer approval for an under-review provider unless the API marks it eligible', async () => {
    const user = userEvent.setup();
    vi.mocked(providersApi.listProviders).mockResolvedValue({
      data: [{
        id: 'provider-not-eligible',
        provider_type: 'DOCTOR',
        name: 'Unresolved Review Doctor',
        email: null,
        phone: null,
        visit_stability: 'NOT_STABLE_VISIT',
        emergency_services_available: false,
        status: 'UNDER_REVIEW',
        publication_status: 'UNPUBLISHED',
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
        thumbnail_url: null,
        average_rating: null,
        review_count: 0,
        approval_available: false,
      }],
      meta: { page: 1, page_size: 10, total: 1, total_pages: 1 },
    });

    render(<MemoryRouter><ProvidersPage /></MemoryRouter>);
    await screen.findByText('Unresolved Review Doctor');
    expect(screen.getByText('Under review')).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'Actions for Unresolved Review Doctor' }));
    const menu = screen.getByRole('menu');
    expect(within(menu).queryByRole('menuitem', { name: 'Approve provider' })).toBeNull();
    expect(within(menu).queryByRole('menuitem', { name: 'Activate' })).toBeNull();
  });

  it('routes direct listings to deliberate contact selection instead of sending to a guessed email', async () => {
    const user = userEvent.setup();
    vi.mocked(providersApi.listProviders).mockResolvedValue({
      data: [{
        id: 'provider-direct',
        provider_type: 'CLINIC',
        name: 'Direct Clinic',
        email: 'only-contact@example.com',
        phone: null,
        visit_stability: 'STABLE_VISIT',
        emergency_services_available: false,
        status: 'ACTIVE',
        publication_status: 'UNPUBLISHED',
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
        thumbnail_url: null,
        average_rating: null,
        review_count: 0,
        portal_access_action: 'setup',
        portal_access_status: 'eligible',
        portal_access_reason: 'A contact email must be explicitly selected before setup.',
        portal_login_email: 'only-contact@example.com',
      }],
      meta: { page: 1, page_size: 10, total: 1, total_pages: 1 },
    });
    render(<MemoryRouter><ProvidersPage /></MemoryRouter>);
    await screen.findByText('Direct Clinic');
    await user.click(screen.getByRole('button', { name: 'Actions for Direct Clinic' }));
    await user.click(screen.getByRole('menuitem', { name: 'Choose email for password setup' }));
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(providersApi.sendProviderPortalAccess).not.toHaveBeenCalled();
  });

  it('shows review summaries and links reviewed providers to scoped moderation', async () => {
    vi.mocked(providersApi.listProviders).mockResolvedValue({
      data: [
        {
          id: 'provider-reviewed',
          provider_type: 'CLINIC',
          name: 'Reviewed Clinic With a Very Long Provider Name',
          email: null,
          phone: null,
          visit_stability: 'STABLE_VISIT',
          emergency_services_available: true,
          status: 'ACTIVE',
          publication_status: 'PUBLISHED',
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z',
          thumbnail_url: null,
          average_rating: 4,
          review_count: 2,
        },
        {
          id: 'provider-empty',
          provider_type: 'DOCTOR',
          name: 'No Reviews Doctor',
          email: null,
          phone: null,
          visit_stability: 'STABLE_VISIT',
          emergency_services_available: false,
          status: 'ACTIVE',
          publication_status: 'UNPUBLISHED',
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z',
          thumbnail_url: null,
          average_rating: null,
          review_count: 0,
        },
      ],
      meta: { page: 1, page_size: 10, total: 2, total_pages: 1 },
    });

    render(<MemoryRouter><ProvidersPage /></MemoryRouter>);

    const fullName = 'Reviewed Clinic With a Very Long Provider Name';
    const nameLink = await screen.findByRole('link', { name: fullName });
    expect(nameLink.getAttribute('href')).toBe('/admin/providers/provider-reviewed');
    expect(nameLink.getAttribute('title')).toBe(fullName);
    expect(screen.getByRole('columnheader', { name: 'Provider name' }).closest<HTMLElement>('[role="row"]')?.style.gridTemplateColumns)
      .toContain('minmax(180px, 1.8fr)');
    expect(screen.getByText('★ 4.0')).toBeTruthy();
    expect(
      screen.getByRole('link', { name: `View 2 reviews for ${fullName}` }).getAttribute('href')
    ).toBe('/admin/reviews?provider_id=provider-reviewed');
    expect(screen.getByText('No Reviews Doctor')).toBeTruthy();
    const reviewedRow = nameLink.closest<HTMLElement>('[role="row"]')!;
    const emptyRow = screen.getByText('No Reviews Doctor').closest<HTMLElement>('[role="row"]')!;
    expect(within(reviewedRow).getByText('Clinic')).toBeTruthy();
    expect(within(within(reviewedRow).getAllByRole('cell')[3]).getByText('Yes')).toBeTruthy();
    expect(within(emptyRow).getByText('Doctor')).toBeTruthy();
    expect(within(within(emptyRow).getAllByRole('cell')[3]).getByText('No')).toBeTruthy();
    expect(screen.getByRole('columnheader', { name: 'Emergency services available' })).toBeTruthy();
    expect(screen.getAllByText('—').length).toBeGreaterThan(0);
  });

  it('uses semantic action icons and keeps provider publication actions working', async () => {
    vi.mocked(providersApi.listProviders).mockResolvedValue({
      data: [{
        id: 'provider-1',
        provider_type: 'CLINIC',
        name: 'Action Clinic',
        email: null,
        phone: null,
        visit_stability: 'STABLE_VISIT',
        emergency_services_available: false,
        status: 'ACTIVE',
        publication_status: 'PUBLISHED',
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
        thumbnail_url: null,
        average_rating: null,
        review_count: 0,
      }],
      meta: { page: 1, page_size: 10, total: 1, total_pages: 1 },
    });
    const user = userEvent.setup();

    render(<MemoryRouter><ProvidersPage /></MemoryRouter>);

    await screen.findByText('Action Clinic');
    await user.click(screen.getByRole('button', { name: 'Actions for Action Clinic' }));

    const menu = screen.getByRole('menu');
    expect(within(menu).getByRole('menuitem', { name: 'View' })).toBeTruthy();
    expect(within(menu).getByRole('menuitem', { name: 'Edit' })).toBeTruthy();
    expect(within(menu).getByRole('menuitem', { name: 'Deactivate' })).toBeTruthy();
    expect(within(menu).getByRole('menuitem', { name: 'Unpublish' })).toBeTruthy();
    expect(menu.querySelector('[data-icon="view"]')).toBeTruthy();
    expect(menu.querySelector('[data-icon="edit"]')).toBeTruthy();
    expect(menu.querySelector('[data-icon="deactivate"]')).toBeTruthy();
    expect(menu.querySelector('[data-icon="unpublish"]')).toBeTruthy();

    await user.click(within(menu).getByRole('menuitem', { name: 'Unpublish' }));
    expect(providersApi.updateProviderPublication).toHaveBeenCalledWith('provider-1', 'UNPUBLISHED');
  });

  it('sends emergency filters with other filters and resets pagination on selection, chip removal and Clear all', async () => {
    const user = userEvent.setup();
    vi.mocked(providersApi.listProviders).mockImplementation(async (params) => ({
      data: [{
        id: 'p1', provider_type: 'CLINIC', name: 'Clinic One', email: null, phone: null,
        visit_stability: 'STABLE_VISIT', emergency_services_available: true,
        status: 'ACTIVE', publication_status: 'PUBLISHED',
        created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
        thumbnail_url: null, average_rating: null, review_count: 0,
      }],
      meta: { page: params?.page ?? 1, page_size: 10, total: 21, total_pages: 3 },
    }));
    render(<MemoryRouter><ProvidersPage /></MemoryRouter>);
    await screen.findByText('Clinic One');
    expect(vi.mocked(providersApi.listProviders).mock.lastCall?.[0]).not.toHaveProperty('emergency_services_available');
    await user.click(screen.getByRole('button', { name: 'Next →' }));
    await waitFor(() => expect(providersApi.listProviders).toHaveBeenLastCalledWith(
      expect.objectContaining({ page: 2 })
    ));

    await user.click(screen.getByRole('button', { name: /Filters/ }));
    await user.click(within(screen.getByRole('group', { name: 'Provider type' })).getByRole('button', { name: 'Clinics' }));
    const emergencyGroup = screen.getByRole('group', { name: 'Emergency services available' });
    const allEmergencyButton = within(emergencyGroup).getByRole('button', { name: 'Emergency services' });
    expect(allEmergencyButton.getAttribute('aria-pressed')).toBe('true');
    await user.click(within(emergencyGroup).getByRole('button', { name: 'Available' }));
    await waitFor(() => expect(providersApi.listProviders).toHaveBeenLastCalledWith(
      expect.objectContaining({ page: 1, provider_type: 'CLINIC', emergency_services_available: true })
    ));
    await user.type(screen.getByRole('searchbox', { name: 'Search by name…' }), 'Clinic');
    await waitFor(() => expect(providersApi.listProviders).toHaveBeenLastCalledWith(
      expect.objectContaining({ page: 1, search: 'Clinic', provider_type: 'CLINIC', emergency_services_available: true })
    ));
    await user.click(within(emergencyGroup).getByRole('button', { name: 'Unavailable' }));
    await waitFor(() => expect(providersApi.listProviders).toHaveBeenLastCalledWith(
      expect.objectContaining({ page: 1, provider_type: 'CLINIC', emergency_services_available: false })
    ));
    await user.click(allEmergencyButton);
    await waitFor(() => expect(providersApi.listProviders).toHaveBeenLastCalledWith(
      expect.objectContaining({ page: 1, provider_type: 'CLINIC', search: 'Clinic' })
    ));
    expect(vi.mocked(providersApi.listProviders).mock.lastCall?.[0]).not.toHaveProperty('emergency_services_available');
    expect(allEmergencyButton.getAttribute('aria-pressed')).toBe('true');
    await user.click(within(emergencyGroup).getByRole('button', { name: 'Unavailable' }));
    await waitFor(() => expect(providersApi.listProviders).toHaveBeenLastCalledWith(
      expect.objectContaining({ page: 1, provider_type: 'CLINIC', emergency_services_available: false })
    ));

    await user.click(screen.getByRole('button', { name: /Filters/ }));
    expect(screen.queryByRole('group', { name: 'Emergency services available' })).toBeNull();
    expect(screen.getByRole('button', { name: /Emergency services available: Unavailable/ })).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'Next →' }));
    await waitFor(() => expect(providersApi.listProviders).toHaveBeenLastCalledWith(
      expect.objectContaining({ page: 2, emergency_services_available: false })
    ));
    await user.click(screen.getByRole('button', { name: /Emergency services available: Unavailable/ }));
    await waitFor(() => expect(providersApi.listProviders).toHaveBeenLastCalledWith(
      expect.objectContaining({ page: 1, provider_type: 'CLINIC', search: 'Clinic' })
    ));
    expect(vi.mocked(providersApi.listProviders).mock.lastCall?.[0]).not.toHaveProperty('emergency_services_available');
    await user.click(screen.getByRole('button', { name: /Filters/ }));
    await user.click(within(screen.getByRole('group', { name: 'Emergency services available' })).getByRole('button', { name: 'Available' }));
    await user.click(screen.getByRole('button', { name: /Filters/ }));
    expect(screen.getByRole('button', { name: /Emergency services available: Available/ })).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'Next →' }));
    await waitFor(() => expect(providersApi.listProviders).toHaveBeenLastCalledWith(
      expect.objectContaining({ page: 2, emergency_services_available: true })
    ));
    await user.click(screen.getByRole('button', { name: /Filters/ }));
    await user.click(screen.getByRole('button', { name: 'Clear all filters' }));
    await waitFor(() => expect(providersApi.listProviders).toHaveBeenLastCalledWith(
      { page: 1, page_size: 10 }
    ));
  });
});