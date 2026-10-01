import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { TimeSettingsProvider } from '@/app/TimeSettingsContext';
import { ProviderDetailPage } from './ProviderDetailPage';
import {
  approveProvider, createProviderVisit, deleteProviderPhoto, getProvider, getProviderPortalAccess, resendProviderApprovalEmail, revokeProviderPortalAccess, sendProviderPortalAccess,
  setProviderThumbnail, updateProviderVisit, uploadProviderPhoto,
} from '@/api/providers';
import type { Provider, ProviderPortalAccess } from '@/types';
import { readFileSync } from 'node:fs';
import styles from './ProviderDetailPage.module.css';

vi.mock('@/api/providers', () => ({
  approveProvider: vi.fn(),
  addProviderSpecialization: vi.fn(),
  createProviderLocation: vi.fn(),
  createProviderVisit: vi.fn(),
  deleteProviderLocation: vi.fn(),
  deleteProviderPhoto: vi.fn(),
  getProvider: vi.fn(),
  getProviderPortalAccess: vi.fn(),
  revokeProviderPortalAccess: vi.fn(),
  resendProviderApprovalEmail: vi.fn(),
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

function pendingAccess(overrides: Partial<ProviderPortalAccess> = {}): ProviderPortalAccess {
  return {
    status: 'pending', recipient_email: 'main@example.com', email_id: 'email-1',
    invitation_id: null, sent_at: '2025-01-01T00:00:00Z', message: null,
    can_revoke: true,
    selectable_emails: [{ email_id: 'email-1', email: 'main@example.com' }],
    ...overrides,
  };
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
  it('offers password reset to a linked login email without a contact-email selector', async () => {
    const linkedAccess: ProviderPortalAccess = {
      status: 'active',
      action: 'reset',
      available: true,
      reason: 'A password reset link can be sent to the linked provider login email.',
      recipient_email: 'login@example.com',
      email_id: null,
      invitation_id: null,
      sent_at: null,
      message: null,
      selectable_emails: [],
      can_revoke: false,
    };
    vi.mocked(getProvider).mockResolvedValue(doctor());
    vi.mocked(getProviderPortalAccess).mockResolvedValue(linkedAccess);
    vi.mocked(sendProviderPortalAccess).mockResolvedValue({
      ...linkedAccess,
      message: 'Password reset email sent to login@example.com.',
    });
    renderDetail();

    const reset = await screen.findByRole('button', { name: 'Send password reset email' });
    expect(screen.queryByRole('combobox', { name: 'Contact email for portal access' })).toBeNull();
    expect(screen.getByText('login@example.com')).toBeTruthy();
    await userEvent.setup().click(reset);
    await waitFor(() => expect(sendProviderPortalAccess).toHaveBeenCalledWith('provider-1'));
    expect(await screen.findByText('Password reset email sent to login@example.com.')).toBeTruthy();
  });

  it('approves under-review providers through the explicit action and explains when setup is needed', async () => {
    vi.mocked(getProvider).mockResolvedValue(doctor({ status: 'UNDER_REVIEW' }));
    vi.mocked(approveProvider).mockResolvedValue({
      message: 'Provider listing approved. The linked account still needs password setup; send a setup email before the provider can sign in.',
      email_sent: false,
    });
    renderDetail();

    expect(await screen.findByRole('button', { name: 'Approve provider' })).toBeTruthy();
    expect(screen.getByText('Under review')).toBeTruthy();
    await userEvent.setup().click(screen.getByRole('button', { name: 'Approve provider' }));
    await waitFor(() => expect(approveProvider).toHaveBeenCalledWith('provider-1'));
    expect(await screen.findByText(/The linked account still needs password setup/)).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Retry approval email' })).toBeNull();
  });

  it('uses defined compact supporting and Locations item typography for every trip period', async () => {
    const address = 'An exceptionally long equine hospital address with a continuous identifier ' + 'A'.repeat(150);
    vi.mocked(getProvider).mockResolvedValue(doctor({
      doctor_visits: [
        { id: 'past', start_date: '2000-01-01', end_date: '2000-01-02', location: { address_line_1: address, city: 'Calgary' } },
        { id: 'current', start_date: '2000-01-01', end_date: '2999-01-01', location: { address_line_1: address, city: 'Calgary' } },
        { id: 'future', start_date: '2999-06-01', end_date: '2999-06-03', location: { address_line_1: address, city: 'Calgary' } },
      ],
    }));
    renderDetail();
    const description = await screen.findByText('Availability and visit locations are recorded as date periods.');
    expect(description.classList.contains(styles.tripDescription)).toBe(true);
    expect(screen.getByRole('heading', { name: 'Doctor trips' }).classList.contains(styles.sectionTitle)).toBe(true);
    for (const period of ['Previous', 'Current', 'Upcoming']) {
      const label = screen.getByText(new RegExp(`^${period} ·`));
      expect(label.classList.contains(styles.itemTitle)).toBe(true);
      expect(label.parentElement!.classList.contains(styles.itemMain)).toBe(true);
      expect(label.parentElement!.classList.contains(styles.tripText)).toBe(true);
      expect(label.nextElementSibling!.classList.contains(styles.itemSub)).toBe(true);
    }
    expect(screen.getAllByRole('button', { name: 'Amend' })).toHaveLength(1);
    // Vitest stubs module imports; check declarations from the actual CSS.
    const style = document.createElement('style');
    style.textContent = readFileSync('src/pages/admin/ProviderDetailPage.module.css', 'utf8');
    document.head.append(style);
    try {
      const rules = Array.from(style.sheet!.cssRules) as CSSStyleRule[];
      const rule = (selector: string) => rules.find((r) => r.selectorText === selector)!.style;
      expect(rule('.tripDescription').getPropertyValue('font-size')).toBe('var(--text-sm)');
      expect(rule('.tripDescription').getPropertyValue('color')).toBe('var(--text-muted)');
      expect(rule('.tripDescription').getPropertyValue('margin')).toBe('var(--space-2) 0 0');
      expect(rule('.itemTitle').getPropertyValue('font-size')).toBe('var(--text-sm)');
      expect(rule('.itemTitle').getPropertyValue('font-weight')).toBe('var(--font-medium)');
      expect(rule('.itemTitle').getPropertyValue('color')).toBe('var(--text-primary)');
      expect(rule('.itemSub').getPropertyValue('font-size')).toBe('var(--text-sm)');
      expect(rule('.itemSub').getPropertyValue('color')).toBe('var(--text-secondary)');
      expect(rule('.tripText > p').getPropertyValue('margin')).toBe('0px');
      expect(rule('.itemMain').getPropertyValue('min-width')).toBe('0px');
      expect(rule('.itemMain').getPropertyValue('gap')).toBe('2px');
      expect(rule('.tripText').getPropertyValue('overflow-wrap')).toBe('anywhere');
      expect(rule('.tripText').getPropertyValue('max-width')).toBe('100%');
      expect(rule('.tripHeader').getPropertyValue('flex-wrap')).toBe('wrap');
      expect(rule('.tripHeader > button').getPropertyValue('flex-shrink')).toBe('0');
    } finally {
      style.remove();
    }
  });

  it('creates a future return and reloads its dates and address', async () => {
    const visit = { id: 'new-trip', start_date: '2999-06-01', end_date: '2999-06-03',
      location: { address_line_1: '1 Prairie Way', city: 'Calgary', name: null,
        state_province: null, country: null, postal_code: null } };
    const refreshed = doctor({ doctor_visits: [visit] });
    vi.mocked(getProvider).mockResolvedValueOnce(doctor()).mockResolvedValue(refreshed);
    vi.mocked(createProviderVisit).mockResolvedValue(refreshed);
    renderDetail();
    fireEvent.click(await screen.findByRole('button', { name: 'Add future return' }));
    for (const [label, value] of Object.entries({
      'Address line 1': '1 Prairie Way', City: 'Calgary', 'Start date': visit.start_date, 'End date': visit.end_date,
    })) fireEvent.change(screen.getByLabelText(label), { target: { value } });
    fireEvent.click(screen.getByRole('button', { name: 'Add return' }));
    await waitFor(() => expect(createProviderVisit).toHaveBeenCalledWith('provider-1', {
      location: visit.location, start_date: visit.start_date, end_date: visit.end_date,
    }));
    expect(await screen.findByText('Upcoming · 2999-06-01 to 2999-06-03')).toBeTruthy();
    expect(screen.getByText('1 Prairie Way, Calgary')).toBeTruthy();
    expect(getProvider).toHaveBeenCalledTimes(2);
  });

  it('groups resend and compact destructive cancel while reserving flexible sizing for the email picker', async () => {
    vi.mocked(getProvider).mockResolvedValue(doctor());
    vi.mocked(getProviderPortalAccess).mockResolvedValue(pendingAccess());
    renderDetail();
    const cancel = await screen.findByRole('button', { name: 'Cancel pending access' });
    const resend = await screen.findByRole('button', { name: 'Resend password setup email' });
    const group = screen.getByRole('group', { name: 'Portal access actions' });
    expect(cancel.parentElement).toBe(group);
    expect(resend.parentElement).toBe(group);
    expect(resend.nextElementSibling).toBe(cancel);
    expect(cancel.className).toContain('btn--sm');
    expect(cancel.className).toContain('btn--danger');
    const email = screen.getByRole('combobox', { name: 'Contact email for portal access' }).parentElement!;
    expect(email.classList.contains(styles.portalAccessEmail)).toBe(true);
    expect(email.parentElement).toBe(group.parentElement);

    // CSS imports are stubbed in Vitest: inspect the real stylesheet and selectors.
    const style = document.createElement('style');
    style.textContent = readFileSync('src/pages/admin/ProviderDetailPage.module.css', 'utf8');
    document.head.append(style);
    try {
      const rules = Array.from(style.sheet!.cssRules) as CSSStyleRule[];
      const rule = (selector: string) => rules.find((r) => r.selectorText === selector)!.style;
      expect(rule('.portalAccessEmail').getPropertyValue('flex-grow')).toBe('1');
      expect(rule('.portalAccessEmail').getPropertyValue('min-width')).toBe('min(100%, 260px)');
      expect(rules.some((r) => r.selectorText === '.portalAccessActions > :first-child')).toBe(false);
      expect(rule('.portalAccessActions').getPropertyValue('flex-wrap')).toBe('wrap');
      expect(rule('.portalAccessButtons').getPropertyValue('flex-wrap')).toBe('wrap');
      expect(rule('.portalAccessButtons').getPropertyValue('max-width')).toBe('100%');
      expect(rule('.portalAccessButtons > button').getPropertyValue('flex')).toBe('0 0 auto');
    } finally {
      style.remove();
    }
  });

  it('keeps cancel available without send controls when revocation is permitted', async () => {
    vi.mocked(getProvider).mockResolvedValue(doctor());
    vi.mocked(getProviderPortalAccess).mockResolvedValue(pendingAccess({ status: 'invitation', invitation_id: 'inv-1' }));
    renderDetail();
    expect(await screen.findByRole('button', { name: 'Cancel pending access' })).toBeTruthy();
    expect(screen.queryByRole('button', { name: /password setup email/i })).toBeNull();
    expect(screen.queryByRole('combobox', { name: 'Contact email for portal access' })).toBeNull();
  });

  it('hides cancel when revocation is not permitted', async () => {
    vi.mocked(getProvider).mockResolvedValue(doctor());
    vi.mocked(getProviderPortalAccess).mockResolvedValue(pendingAccess({ can_revoke: false }));
    renderDetail();
    await screen.findByRole('button', { name: 'Resend password setup email' });
    expect(screen.queryByRole('button', { name: 'Cancel pending access' })).toBeNull();
  });

  it('resends the selected contact and disables both actions and the picker while sending', async () => {
    vi.mocked(getProvider).mockResolvedValue(doctor());
    vi.mocked(getProviderPortalAccess).mockResolvedValue(pendingAccess());
    let finish!: (access: ProviderPortalAccess) => void;
    vi.mocked(sendProviderPortalAccess).mockImplementation(() => new Promise((resolve) => { finish = resolve; }));
    const user = userEvent.setup();
    renderDetail();
    const resend = await screen.findByRole('button', { name: 'Resend password setup email' });
    await user.click(resend);
    expect(sendProviderPortalAccess).toHaveBeenCalledWith('provider-1', 'email-1');
    expect((resend as HTMLButtonElement).disabled).toBe(true);
    expect(resend.getAttribute('aria-busy')).toBe('true');
    expect((screen.getByRole('button', { name: 'Cancel pending access' }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole('combobox', { name: 'Contact email for portal access' }) as HTMLSelectElement).disabled).toBe(true);
    finish(pendingAccess());
    await waitFor(() => expect((resend as HTMLButtonElement).disabled).toBe(false));
  });

  it('requires confirmation and shows loading while canceling, then recovers on failure', async () => {
    vi.mocked(getProvider).mockResolvedValue(doctor());
    vi.mocked(getProviderPortalAccess).mockResolvedValue(pendingAccess());
    let fail!: (error: Error) => void;
    vi.mocked(revokeProviderPortalAccess).mockImplementation(() => new Promise((_resolve, reject) => { fail = reject; }));
    const user = userEvent.setup();
    renderDetail();
    const cancel = await screen.findByRole('button', { name: 'Cancel pending access' });
    await user.click(cancel);
    expect(revokeProviderPortalAccess).not.toHaveBeenCalled();
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Cancel' }));
    expect(revokeProviderPortalAccess).not.toHaveBeenCalled();
    await user.click(cancel);
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Cancel access' }));
    expect(revokeProviderPortalAccess).toHaveBeenCalledWith('provider-1');
    expect(cancel.getAttribute('aria-busy')).toBe('true');
    expect((cancel as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole('button', { name: 'Resend password setup email' }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole('combobox', { name: 'Contact email for portal access' }) as HTMLSelectElement).disabled).toBe(true);
    fail(new Error('Network unavailable'));
    expect(await screen.findByRole('alert')).toBeTruthy();
    await waitFor(() => expect((cancel as HTMLButtonElement).disabled).toBe(false));
    expect(cancel.getAttribute('aria-busy')).toBe('false');
  });

  it.each([false, true])('omits clinic/hospital visits from the services summary when its value is %s', async (visits) => {
    vi.mocked(getProvider).mockResolvedValue(doctor({
      provider_type: 'HOSPITAL',
      clinic_hospital_visit: visits,
      languages: [{ id: 'language-1', name: 'Chinese', code: 'zh', is_active: true }],
      visit_stability: 'STABLE_VISIT',
      maximum_working_radius_km: 50,
      emergency_services_available: true,
      emergency_contact_number: '+91 9867360488',
    }));
    renderDetail();
    expect(await screen.findByRole('heading', { name: 'Services & languages' })).toBeTruthy();
    expect(screen.queryByText('Clinic / hospital visits')).toBeNull();
    expect(screen.getByText('Chinese')).toBeTruthy();
    expect(screen.getByText('Emergency services')).toBeTruthy();
    expect(screen.getByText('50 km')).toBeTruthy();
    expect(screen.getByText('+91 9867360488')).toBeTruthy();
  });

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
    await user.click(screen.getByRole('button', { name: 'Send password setup email' }));
    await waitFor(() => expect(sendProviderPortalAccess).toHaveBeenCalledWith('provider-1', 'email-2'));
    expect(await screen.findByText('Password setup email sent to second@example.com.')).toBeTruthy();
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
    await user.click(screen.getByRole('button', { name: 'Send password setup email' }));
    await waitFor(() => expect(sendProviderPortalAccess).toHaveBeenCalledWith('provider-1', 'email-2'));
    expect(await screen.findByText('Password setup email sent to corrected@example.com.')).toBeTruthy();
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
    expect(screen.queryByRole('button', { name: /password setup email/i })).toBeNull();
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
