import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import * as adminApi from '@/api/admin';
import { ProviderApplicationsPage } from './ProviderApplicationsPage';

vi.mock('@/api/admin', () => ({
  approveProviderApplication: vi.fn(),
  approveProviderProfileUpdate: vi.fn(),
  listProviderApplications: vi.fn(),
  listProviderProfileUpdates: vi.fn(),
  rejectProviderApplication: vi.fn(),
  rejectProviderProfileUpdate: vi.fn(),
}));

vi.mock('@/app/TimeSettingsContext', () => ({
  useTimeSettings: () => ({
    formatTimestamp: (value: string) => `formatted:${value}`,
  }),
}));

const application = {
  id: 'application-1',
  user_id: 'user-1',
  provider_id: null,
  provider_type: 'CLINIC' as const,
  provider_name: 'Austin Equine Clinic',
  visit_stability: 'NOT_STABLE_VISIT' as const,
  review_status: 'PENDING_REVIEW' as const,
  first_name: 'Amina',
  last_name: 'Rider',
  full_name: 'Amina Rider',
  email: 'amina@example.com',
  mobile_number: null,
  professional_title: 'Equine veterinarian',
  specialization_ids: ['spec-1', 'spec-2'],
  specializations: [{ id: 'spec-1', name: 'Equine medicine' }, { id: 'spec-2', name: 'Dentistry' }],
  languages: [{ id: 'lang-1', name: 'English' }, { id: 'lang-2', name: 'Arabic' }],
  years_experience: 0,
  postal_code: '78701',
  working_address: '1200 Longhorn Avenue, Building 4',
  stable_visit: false,
  maximum_working_radius_km: 0,
  emergency_services_available: false,
  emergency_contact_number: '+1 512 555 0148',
  terms_accepted_at: '2026-08-20T08:15:00Z',
  privacy_accepted_at: '2026-08-20T08:16:00Z',
  country: 'United States',
  state_province: 'Texas',
  city: 'Austin',
  email_verified_at: '2026-08-21T12:00:00Z',
  reviewed_by_user_id: null,
  reviewed_by_name: null,
  reviewed_at: null,
  rejection_reason: null,
  created_at: '2026-08-21T12:00:00Z',
};

const profileUpdate = {
  id: 'profile-update-1',
  provider_id: 'provider-1',
  provider_name: 'Austin Equine Clinic',
  provider_type: 'CLINIC' as const,
  review_status: 'PENDING_REVIEW' as const,
  proposed_profile: {
    name: 'Austin Equine Specialists',
    maximum_working_radius_km: 75,
    emergency_services_available: true,
    emergency_contact_number: '+971 501234567',
    experience_description: 'Equine emergency experience',
    visit_stability: 'STABLE_VISIT' as const,
    specialization_ids: [],
    locations: [],
    phones: [],
    emails: [],
    photos: [],
    qualifications: [],
  },
  current_profile: {
    name: 'Austin Equine Clinic',
    maximum_working_radius_km: 25,
    emergency_services_available: false,
    emergency_contact_number: null,
    experience_description: null,
    visit_stability: 'STABLE_VISIT' as const,
    specialization_ids: [],
    locations: [],
    phones: [],
    emails: [],
    photos: [],
    qualifications: [],
  },
  submitted_at: '2026-08-21T12:00:00Z',
  reviewed_by_user_id: null,
  reviewed_by_name: null,
  reviewed_at: null,
  rejection_reason: null,
  created_at: '2026-08-21T12:00:00Z',
};

function response<T>(data: T[], total = data.length) {
  return {
    data,
    meta: { page: 1, page_size: 10, total, total_pages: total === 0 ? 0 : 1 },
  };
}

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

describe('ProviderApplicationsPage', () => {
  it('hides list controls for an unfiltered empty provider application collection', async () => {
    vi.mocked(adminApi.listProviderApplications).mockResolvedValue(response([]));

    render(<MemoryRouter><ProviderApplicationsPage /></MemoryRouter>);

    expect(await screen.findByText('No provider applications yet')).toBeTruthy();
    expect(screen.queryByRole('searchbox')).toBeNull();
    expect(screen.queryByRole('button', { name: 'Filters' })).toBeNull();
    expect(screen.queryByLabelText('Pagination')).toBeNull();
    expect(screen.queryByLabelText('Rows per page')).toBeNull();
    expect(screen.queryByText('Showing 0 to 0 of 0 entries')).toBeNull();
  });

  it('shows list controls and pagination for a single provider application', async () => {
    vi.mocked(adminApi.listProviderApplications).mockResolvedValue(response([application]));
    const user = userEvent.setup();

    render(<MemoryRouter><ProviderApplicationsPage /></MemoryRouter>);

    expect(await screen.findByText('Austin Equine Clinic')).toBeTruthy();
    expect(screen.getByRole('searchbox')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Filters' })).toBeTruthy();
    expect(screen.getByLabelText('Pagination')).toBeTruthy();
    const pageSize = screen.getByLabelText('Rows per page');
    expect(screen.getByText('Showing 1 to 1 of 1 entries')).toBeTruthy();
    expect(screen.getByRole('button', { name: /Previous/ }).hasAttribute('disabled')).toBe(true);
    expect(screen.getByRole('button', { name: /Next/ }).hasAttribute('disabled')).toBe(true);

    await user.selectOptions(pageSize, '25');
    await waitFor(() => expect(adminApi.listProviderApplications).toHaveBeenLastCalledWith(
      expect.objectContaining({ page: 1, page_size: 25 }),
    ));
  });

  it('keeps list controls available when active criteria return no provider applications', async () => {
    vi.mocked(adminApi.listProviderApplications).mockResolvedValue(response([]));

    render(
      <MemoryRouter initialEntries={['/admin/provider-applications?search=missing@example.com']}>
        <ProviderApplicationsPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText('No provider applications found')).toBeTruthy();
    expect(screen.getByRole('searchbox')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Filters' })).toBeTruthy();
    expect(screen.getByLabelText('Pagination')).toBeTruthy();
    expect(screen.getByLabelText('Rows per page')).toBeTruthy();
  });

  it('shows all application details without losing explicit false, zero, separate names, selections, or consent times', async () => {
    vi.mocked(adminApi.listProviderApplications).mockResolvedValue(response([application]));
    const user = userEvent.setup();
    render(<MemoryRouter><ProviderApplicationsPage /></MemoryRouter>);

    await user.click(await screen.findByLabelText('Actions for Austin Equine Clinic'));
    await user.click(await screen.findByText('View application'));
    const dialog = await screen.findByRole('dialog', { name: 'Provider application' });
    expect(within(dialog).getByText('Amina')).toBeTruthy();
    expect(within(dialog).getByText('Rider')).toBeTruthy();
    expect(within(dialog).getByText('Equine veterinarian')).toBeTruthy();
    expect(within(dialog).getByText('Equine medicine')).toBeTruthy();
    expect(within(dialog).getByText('Dentistry')).toBeTruthy();
    expect(within(dialog).getByText('English')).toBeTruthy();
    expect(within(dialog).getByText('Arabic')).toBeTruthy();
    expect(within(dialog).getAllByText('0')).toHaveLength(2);
    expect(within(dialog).getAllByText('No').length).toBeGreaterThanOrEqual(2);
    expect(within(dialog).getByText('Accepted · formatted:2026-08-20T08:15:00Z')).toBeTruthy();
    expect(within(dialog).getByText('Accepted · formatted:2026-08-20T08:16:00Z')).toBeTruthy();
    expect(within(dialog).getByText('1200 Longhorn Avenue, Building 4')).toBeTruthy();
    expect(within(dialog).getByText('78701')).toBeTruthy();
  });

  it('shows null application history and missing consents as not provided without deriving stable visits from legacy metadata', async () => {
    const sparseApplication = {
      ...application,
      first_name: null,
      last_name: null,
      professional_title: null,
      specialization_ids: null,
      specializations: null,
      languages: [],
      years_experience: null,
      postal_code: null,
      working_address: null,
      stable_visit: null,
      maximum_working_radius_km: null,
      emergency_services_available: null,
      emergency_contact_number: null,
      terms_accepted_at: null,
      privacy_accepted_at: null,
      reviewed_at: null,
      reviewed_by_name: null,
      rejection_reason: null,
      visit_stability: 'STABLE_VISIT' as const,
    };
    vi.mocked(adminApi.listProviderApplications).mockResolvedValue(response([sparseApplication]));
    const user = userEvent.setup();
    render(<MemoryRouter><ProviderApplicationsPage /></MemoryRouter>);

    await user.click(await screen.findByLabelText('Actions for Austin Equine Clinic'));
    await user.click(await screen.findByText('View application'));
    const dialog = await screen.findByRole('dialog', { name: 'Provider application' });
    expect(within(dialog).getAllByText('Not provided').length).toBeGreaterThanOrEqual(12);
    const stableRow = within(dialog).getByText('Stable visits available').parentElement;
    expect(stableRow).toBeTruthy();
    expect(within(stableRow as HTMLElement).getByText('Not provided')).toBeTruthy();
    expect(within(dialog).getByText('Legacy visit classification')).toBeTruthy();
  });

  it('approves a pending provider application only after confirmation and preserves the returned review state', async () => {
    vi.mocked(adminApi.listProviderApplications).mockResolvedValue(response([application]));
    vi.mocked(adminApi.approveProviderApplication).mockResolvedValue({ ...application, review_status: 'APPROVED' });
    const user = userEvent.setup();
    render(<MemoryRouter><ProviderApplicationsPage /></MemoryRouter>);

    await user.click(await screen.findByLabelText('Actions for Austin Equine Clinic'));
    await user.click(await screen.findByText('View application'));
    const review = await screen.findByRole('dialog', { name: 'Provider application' });
    await user.click(within(review).getByRole('button', { name: 'Approve & stage listing' }));
    const confirmation = await screen.findByRole('dialog', { name: 'Approve provider application?' });
    expect(adminApi.approveProviderApplication).not.toHaveBeenCalled();
    await user.click(within(confirmation).getByRole('button', { name: 'Approve application' }));

    await waitFor(() => expect(adminApi.approveProviderApplication).toHaveBeenCalledWith('application-1'));
    expect(await screen.findByText('APPROVED')).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Approve & stage listing' })).toBeNull();
  });

  it('rejects a pending provider application only after confirmation and preserves the returned reason', async () => {
    vi.mocked(adminApi.listProviderApplications).mockResolvedValue(response([application]));
    vi.mocked(adminApi.rejectProviderApplication).mockResolvedValue({
      ...application,
      review_status: 'REJECTED',
      rejection_reason: 'Registration details need correction.',
    });
    const user = userEvent.setup();
    render(<MemoryRouter><ProviderApplicationsPage /></MemoryRouter>);

    await user.click(await screen.findByLabelText('Actions for Austin Equine Clinic'));
    await user.click(await screen.findByText('View application'));
    const review = await screen.findByRole('dialog', { name: 'Provider application' });
    await user.click(within(review).getByRole('button', { name: 'Reject' }));
    const confirmation = await screen.findByRole('dialog', { name: 'Reject provider application?' });
    await user.click(within(confirmation).getByRole('button', { name: 'Reject application' }));

    await waitFor(() => expect(adminApi.rejectProviderApplication).toHaveBeenCalledWith('application-1'));
    expect(await screen.findByText('REJECTED')).toBeTruthy();
    expect(screen.getByText('Registration details need correction.')).toBeTruthy();
  });

  it('keeps decisions unavailable for reviewed applications', async () => {
    vi.mocked(adminApi.listProviderApplications).mockResolvedValue(response([{ ...application, review_status: 'APPROVED' }]));
    const user = userEvent.setup();
    render(<MemoryRouter><ProviderApplicationsPage /></MemoryRouter>);

    await user.click(await screen.findByLabelText('Actions for Austin Equine Clinic'));
    await user.click(await screen.findByText('View application'));
    const review = await screen.findByRole('dialog', { name: 'Provider application' });
    expect(within(review).queryByRole('button', { name: 'Approve & stage listing' })).toBeNull();
    expect(within(review).queryByRole('button', { name: 'Reject' })).toBeNull();
  });

  it('Escape cancels decision confirmation without closing the application underneath', async () => {
    vi.mocked(adminApi.listProviderApplications).mockResolvedValue(response([application]));
    const user = userEvent.setup();
    render(<MemoryRouter><ProviderApplicationsPage /></MemoryRouter>);

    await user.click(await screen.findByLabelText('Actions for Austin Equine Clinic'));
    await user.click(await screen.findByText('View application'));
    const review = await screen.findByRole('dialog', { name: 'Provider application' });
    await user.click(within(review).getByRole('button', { name: 'Approve & stage listing' }));
    expect(await screen.findByRole('dialog', { name: 'Approve provider application?' })).toBeTruthy();
    await user.keyboard('{Escape}');
    await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Approve provider application?' })).toBeNull());
    expect(screen.getByRole('dialog', { name: 'Provider application' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Approve & stage listing' })).toBeTruthy();
    expect(adminApi.approveProviderApplication).not.toHaveBeenCalled();
  });

  it('separates published profile updates into the Updates tab', async () => {
    vi.mocked(adminApi.listProviderApplications).mockResolvedValue(response([]));
    vi.mocked(adminApi.listProviderProfileUpdates).mockResolvedValue({
      data: [profileUpdate],
      meta: { page: 1, page_size: 100, total: 1, total_pages: 1 },
    });
    const user = userEvent.setup();

    render(
      <MemoryRouter initialEntries={['/admin/provider-applications?tab=updates']}>
        <ProviderApplicationsPage />
      </MemoryRouter>,
    );

    expect(await screen.findByLabelText('Actions for Austin Equine Clinic update')).toBeTruthy();
    expect(screen.getByRole('tab', { name: 'Updates' }).getAttribute('aria-selected')).toBe('true');
    await user.click(screen.getByLabelText('Actions for Austin Equine Clinic update'));
    await user.click(await screen.findByText('Compare profiles'));
    expect(await screen.findByText('Current approved')).toBeTruthy();
    expect(screen.getAllByText('Austin Equine Clinic').length).toBeGreaterThan(1);
    expect(screen.getByText('Austin Equine Specialists')).toBeTruthy();
  });

  it('approves a pending provider profile update from its comparison dialog', async () => {
    vi.mocked(adminApi.listProviderProfileUpdates).mockResolvedValue({
      data: [profileUpdate],
      meta: { page: 1, page_size: 100, total: 1, total_pages: 1 },
    });
    vi.mocked(adminApi.approveProviderProfileUpdate).mockResolvedValue({
      ...profileUpdate,
      review_status: 'APPROVED',
    });
    const user = userEvent.setup();
    render(<MemoryRouter initialEntries={['/admin/provider-applications?tab=updates']}><ProviderApplicationsPage /></MemoryRouter>);

    await user.click(await screen.findByLabelText('Actions for Austin Equine Clinic update'));
    await user.click(await screen.findByText('Compare profiles'));
    const review = await screen.findByRole('dialog', { name: 'Review provider profile update' });
    const radiusRow = within(review).getByRole('row', { name: 'Maximum working radius (km) 25 75' });
    expect(within(radiusRow).getByRole('cell', { name: '75' })).toBeTruthy();
    expect(within(review).getByRole('row', { name: 'Emergency services available No Yes' })).toBeTruthy();
    expect(within(review).getByRole('row', { name: 'Emergency contact number — +971 501234567' })).toBeTruthy();
    expect(within(review).getByRole('row', { name: 'Experience notes — Equine emergency experience' })).toBeTruthy();
    await user.click(within(review).getByRole('button', { name: 'Approve update' }));
    const confirmation = await screen.findByRole('dialog', { name: 'Approve profile update?' });
    await user.click(within(confirmation).getByRole('button', { name: 'Approve update' }));

    await waitFor(() => expect(adminApi.approveProviderProfileUpdate).toHaveBeenCalledWith('profile-update-1'));
  });

  it('records administrator feedback when rejecting a provider profile update', async () => {
    vi.mocked(adminApi.listProviderProfileUpdates).mockResolvedValue({
      data: [profileUpdate],
      meta: { page: 1, page_size: 100, total: 1, total_pages: 1 },
    });
    vi.mocked(adminApi.rejectProviderProfileUpdate).mockResolvedValue({
      ...profileUpdate,
      review_status: 'REJECTED',
      rejection_reason: 'Please verify the new location details.',
    });
    const user = userEvent.setup();
    render(<MemoryRouter initialEntries={['/admin/provider-applications?tab=updates']}><ProviderApplicationsPage /></MemoryRouter>);

    await user.click(await screen.findByLabelText('Actions for Austin Equine Clinic update'));
    await user.click(await screen.findByText('Compare profiles'));
    const review = await screen.findByRole('dialog', { name: 'Review provider profile update' });
    await user.click(within(review).getByRole('button', { name: 'Reject update' }));
    const confirmation = await screen.findByRole('dialog', { name: 'Reject profile update?' });
    await user.type(within(confirmation).getByRole('textbox'), 'Please verify the new location details.');
    await user.click(within(confirmation).getByRole('button', { name: 'Reject update' }));

    await waitFor(() => expect(adminApi.rejectProviderProfileUpdate).toHaveBeenCalledWith(
      'profile-update-1',
      'Please verify the new location details.',
    ));
  });
});