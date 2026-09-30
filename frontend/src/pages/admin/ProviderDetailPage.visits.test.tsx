import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { TimeSettingsProvider } from '@/app/TimeSettingsContext';
import { ProviderDetailPage } from './ProviderDetailPage';
import {
  deleteProviderPhoto, getProvider, getProviderPortalAccess, revokeProviderPortalAccess, sendProviderPortalAccess,
  setProviderThumbnail, updateProviderVisit, uploadProviderPhoto,
} from '@/api/providers';
import type { Provider, ProviderPortalAccess } from '@/types';

vi.mock('@/api/providers', () => ({
  addProviderSpecialization: vi.fn(),
  createProviderLocation: vi.fn(),
  createProviderVisit: vi.fn(),
  deleteProviderLocation: vi.fn(),
  deleteProviderPhoto: vi.fn(),
  getProvider: vi.fn(),
  getProviderPortalAccess: vi.fn(),
  revokeProviderPortalAccess: vi.fn(),
  removeProviderSpecialization: vi.fn(),
  setProviderThumbnail: vi.fn(),
  sendProviderPortalAccess: vi.fn(),
  updateProviderLocation: vi.fn(),
  updateProviderPublication: vi.fn(),
  updateProviderStatus: vi.fn(),
  updateProviderVisit: vi.fn(),
  uploadProviderPhoto: vi.fn(),
}));

vi.mock('@/api/specializations', () => ({
  listSpecializations: vi.fn().mockResolvedValue({
    data: [], meta: { page: 1, page_size: 100, total: 0, total_pages: 1 },
  }),
}));

function doctor(overrides: Partial<Provider> = {}): Provider {
  return {
    id: 'provider-1', provider_type: 'DOCTOR', name: 'Prairie Equine Care',
    description: null, website: null, email: null, phone: null,
    visit_stability: 'NOT_STABLE_VISIT', status: 'ACTIVE', publication_status: 'UNPUBLISHED',
    specializations: [], languages: [], locations: [], photos: [], phones: [], emails: [],
    qualifications: [], thumbnail_url: null, doctor_profile: null,
    maximum_working_radius_km: null, clinic_hospital_visit: false,
    emergency_services_available: false, emergency_contact_name: null, emergency_contact_number: null,
    doctor_availability: 'VISITING', doctor_visits: [], ...overrides,
  } as Provider;
}

function renderDetail() {
  return render(
    <TimeSettingsProvider>
      <MemoryRouter initialEntries={['/admin/providers/provider-1']}>
        <Routes>
          <Route path="/admin/providers/:id" element={<ProviderDetailPage />} />
        </Routes>
      </MemoryRouter>
    </TimeSettingsProvider>
  );
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

beforeEach(() => {
  vi.mocked(getProviderPortalAccess).mockResolvedValue({
    status: 'eligible', recipient_email: null, email_id: null, invitation_id: null,
    sent_at: null, message: null,
    can_revoke: false,
    selectable_emails: [
      { email_id: 'email-1', email: 'main@example.com' },
      { email_id: 'email-2', email: 'second@example.com' },
    ],
  });
});

describe('ProviderDetailPage doctor visits', () => {
  it('lets admins select a contact and send access for an older eligible listing', async () => {
    vi.mocked(getProvider).mockResolvedValue(doctor());
    vi.mocked(sendProviderPortalAccess).mockResolvedValue({
      status: 'pending', recipient_email: 'second@example.com', email_id: 'email-2',
      invitation_id: null, sent_at: '2025-01-01T00:00:00Z', message: null,
      can_revoke: true,
      selectable_emails: [
        { email_id: 'email-1', email: 'main@example.com' },
        { email_id: 'email-2', email: 'second@example.com' },
      ],
    });
    const user = userEvent.setup();
    renderDetail();
    const emailSelect = await screen.findByRole('combobox', { name: 'Contact email for portal access' });
    await user.selectOptions(emailSelect, 'email-2');
    await user.click(screen.getByRole('button', { name: 'Send portal access email' }));
    await waitFor(() => expect(sendProviderPortalAccess).toHaveBeenCalledWith('provider-1', 'email-2'));
    expect(await screen.findByText('Portal access email sent to second@example.com.')).toBeTruthy();
  });

  it('cancels pending access before resending to the corrected contact email', async () => {
    const contacts = [
      { email_id: 'email-1', email: 'old@example.com' },
      { email_id: 'email-2', email: 'corrected@example.com' },
    ];
    vi.mocked(getProvider).mockResolvedValue(doctor());
    vi.mocked(getProviderPortalAccess)
      .mockResolvedValueOnce({
        status: 'pending', recipient_email: 'old@example.com', email_id: 'email-1',
        invitation_id: null, sent_at: '2025-01-01T00:00:00Z', message: null,
        selectable_emails: contacts, can_revoke: true,
      })
      .mockResolvedValueOnce({
        status: 'eligible', recipient_email: null, email_id: null,
        invitation_id: null, sent_at: null, message: null,
        selectable_emails: contacts, can_revoke: false,
      })
      .mockResolvedValueOnce({
        status: 'pending', recipient_email: 'corrected@example.com', email_id: 'email-2',
        invitation_id: null, sent_at: '2025-01-02T00:00:00Z', message: null,
        selectable_emails: contacts, can_revoke: true,
      });
    vi.mocked(revokeProviderPortalAccess).mockResolvedValue({
      status: 'eligible', recipient_email: null, email_id: null,
      invitation_id: null, sent_at: null, message: 'Pending access canceled.',
      selectable_emails: contacts, can_revoke: false,
    });
    vi.mocked(sendProviderPortalAccess).mockResolvedValue({
      status: 'pending', recipient_email: 'corrected@example.com', email_id: 'email-2',
      invitation_id: null, sent_at: '2025-01-02T00:00:00Z', message: null,
      selectable_emails: contacts, can_revoke: true,
    });

    const user = userEvent.setup();
    renderDetail();
    await screen.findByRole('button', { name: 'Cancel pending access' });
    expect(screen.getByText('Recipient').nextElementSibling?.textContent).toBe('old@example.com');
    await user.click(await screen.findByRole('button', { name: 'Cancel pending access' }));

    const dialog = screen.getByRole('dialog');
    expect(within(dialog).getByText(/invalidates the pending setup link and permanently removes the unactivated account/i)).toBeTruthy();
    await user.click(within(dialog).getByRole('button', { name: 'Cancel access' }));
    await waitFor(() => expect(revokeProviderPortalAccess).toHaveBeenCalledWith('provider-1'));
    expect(await screen.findByText('Pending access canceled.')).toBeTruthy();

    const emailSelect = screen.getByRole('combobox', { name: 'Contact email for portal access' });
    await user.selectOptions(emailSelect, 'email-2');
    await user.click(screen.getByRole('button', { name: 'Send portal access email' }));
    await waitFor(() => expect(sendProviderPortalAccess).toHaveBeenCalledWith('provider-1', 'email-2'));
    expect(await screen.findByText('Portal access email sent to corrected@example.com.')).toBeTruthy();
    expect(getProviderPortalAccess).toHaveBeenCalledTimes(3);
  });

  it('directs completed invitees to their invitation instead of a direct send', async () => {
    vi.mocked(getProvider).mockResolvedValue(doctor());
    vi.mocked(getProviderPortalAccess).mockResolvedValue({
      status: 'invitation', recipient_email: 'main@example.com', email_id: null,
      invitation_id: 'inv-1', sent_at: null, message: 'Use Send portal access in the completed invitation.',
      can_revoke: false,
      selectable_emails: [],
    } satisfies ProviderPortalAccess);
    renderDetail();
    expect(await screen.findByRole('link', { name: 'Open invitation workflow' })).toBeTruthy();
    expect(screen.queryByRole('button', { name: /portal access email/i })).toBeNull();
  });

  it('uploads the first gallery photo and displays the saved profile-photo badge', async () => {
    let current = doctor();
    vi.mocked(getProvider).mockImplementation(async () => current);
    vi.mocked(uploadProviderPhoto).mockImplementation(async () => {
      const uploaded = { id: 'first', provider_id: 'provider-1',
        storage_reference: '/uploads/first.png', is_thumbnail: true, display_order: 0,
        alt_text: null, caption: null, created_at: '', updated_at: '' };
      current = doctor({ photos: [uploaded], thumbnail_url: uploaded.storage_reference });
      return uploaded;
    });
    const user = userEvent.setup();

    const view = renderDetail();
    await user.click(await screen.findByRole('button', { name: /Add photos/ }));
    const fileInput = view.container.querySelector('input[type="file"]') as HTMLInputElement;
    await user.upload(fileInput, new File(['image'], 'first.png', { type: 'image/png' }));
    await user.click(await screen.findByRole('button', { name: 'Upload photo' }));
    await waitFor(() => expect(uploadProviderPhoto).toHaveBeenCalledTimes(1));
    expect(await screen.findByText('Profile photo')).toBeTruthy();
    expect(current.thumbnail_url).toBe('/uploads/first.png');
  });

  it('shows gallery profile-photo selection after switching, deleting, and reloading', async () => {
    const photos = [
      { id: 'one', provider_id: 'provider-1', storage_reference: '/uploads/one.jpg',
        is_thumbnail: true, display_order: 0, alt_text: null, caption: null, created_at: '', updated_at: '' },
      { id: 'two', provider_id: 'provider-1', storage_reference: '/uploads/two.jpg',
        is_thumbnail: false, display_order: 1, alt_text: null, caption: null, created_at: '', updated_at: '' },
    ];
    let current = doctor({ photos, thumbnail_url: photos[0].storage_reference });
    vi.mocked(getProvider).mockImplementation(async () => current);
    vi.mocked(setProviderThumbnail).mockImplementation(async (_id, photoId) => {
      current = doctor({ photos: photos.map(p => ({ ...p, is_thumbnail: p.id === photoId })),
        thumbnail_url: photos.find(p => p.id === photoId)!.storage_reference });
      return current.photos.find(p => p.id === photoId)!;
    });
    vi.mocked(deleteProviderPhoto).mockImplementation(async (_id, photoId) => {
      const remaining = current.photos.filter(p => p.id !== photoId);
      current = doctor({ photos: remaining.map((p, i) => ({ ...p, is_thumbnail: i === 0 })),
        thumbnail_url: remaining[0]?.storage_reference ?? null });
    });
    const user = userEvent.setup();

    renderDetail();
    expect(await screen.findByText('Profile photo')).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'Set as profile photo' }));
    await waitFor(() => expect(setProviderThumbnail).toHaveBeenCalledWith('provider-1', 'two'));
    expect(await screen.findByText('Profile photo')).toBeTruthy();
    cleanup();
    renderDetail();
    await screen.findByText('Profile photo');
    expect(current.thumbnail_url).toBe('/uploads/two.jpg');
    const selectedCard = screen.getByText('Profile photo').closest('div[class*="photoCard"]')!;
    await user.click(selectedCard.querySelector('button[class*="removeBtn"]')!);
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Remove' }));
    await waitFor(() => expect(deleteProviderPhoto).toHaveBeenCalledWith('provider-1', 'two'));
    expect(current.thumbnail_url).toBe('/uploads/one.jpg');
  });

  it('displays a non-Doctor provider years of experience, including zero', async () => {
    vi.mocked(getProvider).mockResolvedValue(doctor({
      provider_type: 'CLINIC',
      years_experience: 0,
    }));

    renderDetail();

    const experienceLabel = await screen.findByText('Years of experience');
    expect(experienceLabel.nextElementSibling?.textContent).toBe('0');
  });

  it('shows doctor professional names but not the general provider description', async () => {
    vi.mocked(getProvider).mockResolvedValue(doctor({
      name: 'Mira Stone', description: 'Hidden general description',
      doctor_profile: { first_name: 'Mira', last_name: 'Stone', professional_title: null,
        biography: 'Equine specialist', years_experience: null, experience_description: null },
    } as Provider));
    renderDetail();
    expect(await screen.findByRole('heading', { name: 'Professional info' })).toBeTruthy();
    expect(screen.getByText('Mira')).toBeTruthy();
    expect(screen.getByText('Stone')).toBeTruthy();
    expect(screen.getByText('Equine specialist')).toBeTruthy();
    expect(screen.queryByText('Hidden general description')).toBeNull();
  });
  it('shows the exact empty visiting state and reloads after amending an upcoming trip', async () => {
    const empty = doctor();
    const upcoming = {
      id: 'visit-1',
      location: {
        address_line_1: '1 Prairie Way', city: 'Calgary', name: 'North paddock',
        state_province: 'Alberta', country: 'Canada', postal_code: 'T2P 1J9',
      },
      start_date: '2999-06-01', end_date: '2999-06-03',
    };
    const refreshed = doctor({ doctor_visits: [{ ...upcoming, location: { ...upcoming.location, address_line_1: '2 Prairie Way' } }] });
    vi.mocked(getProvider).mockResolvedValueOnce(empty).mockResolvedValueOnce(refreshed);
    vi.mocked(updateProviderVisit).mockResolvedValue(refreshed);

    renderDetail();
    expect(await screen.findByText('No visit scheduled yet')).toBeTruthy();

    // Simulate the provider returning an upcoming period after a first refresh.
    vi.mocked(getProvider).mockResolvedValueOnce(refreshed);
    await waitFor(() => expect(getProvider).toHaveBeenCalledTimes(1));
    // Reload through the page's existing retry-safe data path by remounting.
    cleanup();
    renderDetail();
    expect(await screen.findByText(/Upcoming · 2999-06-01 to 2999-06-03/)).toBeTruthy();

    await userEvent.setup().click(screen.getByRole('button', { name: 'Amend' }));
    const address = screen.getByLabelText('Address line 1') as HTMLInputElement;
    await userEvent.setup().clear(address);
    await userEvent.setup().type(address, '2 Prairie Way');
    await userEvent.setup().click(screen.getByRole('button', { name: 'Save amendment' }));

    await waitFor(() => expect(updateProviderVisit).toHaveBeenCalledWith('provider-1', 'visit-1', expect.objectContaining({
      start_date: '2999-06-01',
      end_date: '2999-06-03',
      location: expect.objectContaining({ address_line_1: '2 Prairie Way', city: 'Calgary' }),
    })));
    await waitFor(() => expect(getProvider).toHaveBeenCalledTimes(3));
    expect(await screen.findByText(/2 Prairie Way, Calgary/)).toBeTruthy();
  });
});
