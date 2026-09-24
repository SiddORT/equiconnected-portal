import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { ProviderForm, type InvitationFormConfig } from './ProviderForm';
import type { InvitationDraftProvider, Provider } from '@/types';
import {
  addProviderEmail, addProviderPhone, addProviderSpecialization, createProvider,
  getProvider, removeProviderEmail, removeProviderPhone, removeProviderSpecialization,
  updateProvider, updateProviderLocation, updateProviderPublication, updateProviderStatus,
  uploadProviderPhoto,
} from '@/api/providers';
import { lookupProviderPostalCode } from '@/api/auth';
import { listSpecializations } from '@/api/specializations';
import { listLanguages } from '@/api/languages';

vi.mock('@/api/providers', () => ({
  addProviderEmail: vi.fn(),
  addProviderPhone: vi.fn(),
  addProviderSpecialization: vi.fn(),
  createProvider: vi.fn(),
  createProviderLocation: vi.fn(),
  getProvider: vi.fn(),
  removeProviderEmail: vi.fn(),
  removeProviderPhone: vi.fn(),
  removeProviderSpecialization: vi.fn(),
  updateProvider: vi.fn(),
  updateProviderLocation: vi.fn(),
  updateProviderPublication: vi.fn(),
  updateProviderStatus: vi.fn(),
  uploadProviderPhoto: vi.fn(),
}));

vi.mock('@/api/doctors', () => ({
  addDoctorQualification: vi.fn(),
  updateDoctorQualification: vi.fn(),
  deleteDoctorQualification: vi.fn(),
}));
vi.mock('@/api/auth', () => ({
  lookupProviderPostalCode: vi.fn().mockResolvedValue({ status: 'no_match', candidates: [] }),
}));

vi.mock('@/api/specializations', () => ({
  listSpecializations: vi.fn().mockResolvedValue({
    data: [],
    meta: { page: 1, page_size: 100, total: 0, total_pages: 1 },
  }),
}));

vi.mock('@/api/languages', () => ({
  listLanguages: vi.fn().mockResolvedValue({
    data: [{ id: 'lang-en', name: 'English', code: 'en', is_active: true }],
    meta: { page: 1, page_size: 100, total: 0, total_pages: 1 },
  }),
}));

const invitationProvider: InvitationDraftProvider = {
  name: 'Cedar Ridge Clinic',
  description: 'Equine care',
  email: null,
  phone: null,
  website: null,
  visit_stability: 'STABLE_VISIT',
  status: 'ACTIVE',
  specialization_ids: [],
  locations: [],
  phones: [],
  emails: [],
  photos: [],
};

function existingProvider(overrides: Partial<Provider> = {}): Provider {
  return {
    id: 'provider-1', provider_type: 'CLINIC', name: 'Cedar Ridge',
    description: null, website: null, email: null, phone: null,
    visit_stability: 'NOT_STABLE_VISIT', status: 'ACTIVE', publication_status: 'UNPUBLISHED',
    specializations: [{ id: 'spec-1', name: 'Old specialty', is_active: false }],
    languages: [{ id: 'lang-en', name: 'English', code: 'en', is_active: true }],
    locations: [{ id: 'location-1', provider_id: 'provider-1', name: 'Main branch',
      address_line_1: '12 Main St', address_line_2: null, city: 'Calgary',
      state_province: 'Alberta', country: 'Canada', postal_code: 'T2P 1J9',
      latitude: null, longitude: null, is_primary: true, created_at: '', updated_at: '' }],
    emails: [{ id: 'email-1', provider_id: 'provider-1', email: 'old@example.com', is_primary: true, created_at: '', updated_at: '' }],
    phones: [{ id: 'phone-1', provider_id: 'provider-1', country_code: '+1', number: '4035550100', is_primary: true, created_at: '', updated_at: '' }],
    photos: [], thumbnail_url: null, doctor_profile: null, qualifications: [],
    maximum_working_radius_km: null, clinic_hospital_visit: true,
    emergency_services_available: true, emergency_contact_name: 'Dispatch',
    emergency_contact_number: '+1 403 555 9999',
    ...overrides,
  } as Provider;
}

async function reachEditReview(user: ReturnType<typeof userEvent.setup>, doctor = false) {
  await user.click(screen.getByRole('button', { name: 'Continue' }));
  if (doctor) await user.click(screen.getByRole('button', { name: 'Continue' }));
  await user.click(screen.getByRole('button', { name: 'Continue' }));
  await user.click(screen.getByRole('button', { name: 'Continue' }));
  expect(screen.getByRole('heading', { name: 'Review & save' })).toBeTruthy();
}

function invitationConfig(
  overrides: Partial<InvitationDraftProvider> = {},
  onSaveDraft: InvitationFormConfig['onSaveDraft'] = vi.fn().mockResolvedValue(undefined),
  onSubmit: InvitationFormConfig['onSubmit'] = vi.fn().mockResolvedValue(undefined),
): InvitationFormConfig {
  return {
    providerType: 'CLINIC',
    initial: { ...invitationProvider, ...overrides },
    loadSpecializations: vi.fn().mockResolvedValue([]),
    onSaveDraft,
    onSubmit,
  };
}

function CurrentPath() {
  return <output aria-label="Current path">{useLocation().pathname}</output>;
}

afterEach(() => { cleanup(); vi.clearAllMocks(); });

async function beginAdminWizard(type = 'CLINIC') {
  const user = userEvent.setup();
  await user.selectOptions(screen.getByRole('combobox', { name: 'Provider type' }), type);
  await user.type(screen.getByLabelText('Provider / practice name'), 'North Star');
  await user.click(screen.getByRole('button', { name: 'Continue' }));
  return user;
}

async function finishClinicWizard(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole('button', { name: 'Continue' }));
  await user.click(screen.getByRole('button', { name: /Add email/i }));
  await user.type(screen.getByRole('textbox', { name: 'Email address 1' }), 'clinic@example.com');
  await user.type(screen.getByLabelText('Address line 1'), '42 Stable Road');
  await user.type(screen.getByLabelText('Pincode / postal code'), 'T2P 1J9');
  await user.click(screen.getByRole('button', { name: 'Country' }));
  await user.type(screen.getByRole('combobox', { name: 'Search country' }), 'Canada');
  await user.click(screen.getByRole('option', { name: 'Canada' }));
  await user.click(screen.getByRole('button', { name: 'State / Province' }));
  await user.type(screen.getByRole('combobox', { name: 'Search state / province' }), 'Alberta');
  await user.click(screen.getByRole('option', { name: 'Alberta' }));
  await user.click(screen.getByRole('button', { name: 'City' }));
  await user.type(screen.getByRole('combobox', { name: 'Search city' }), 'Calgary');
  await user.click(screen.getByRole('option', { name: 'Calgary' }));
  await user.click(screen.getByRole('button', { name: 'Continue' }));
}

describe('ProviderForm visit stability', () => {
  it('uses Yes and No labels in invitation mode while preserving enum values and saved selection', () => {
    render(<ProviderForm invitation={invitationConfig()} />);

    const select = screen.getByRole('combobox', { name: 'Visit Stable' }) as HTMLSelectElement;
    expect(Array.from(select.options).map((option) => [option.text, option.value])).toEqual([
      ['Select…', ''],
      ['Yes', 'STABLE_VISIT'],
      ['No', 'NOT_STABLE_VISIT'],
    ]);
    expect(select.value).toBe('STABLE_VISIT');
  });

  it('restores a saved non-stable invitation selection as No', () => {
    render(
      <ProviderForm
        invitation={invitationConfig({ visit_stability: 'NOT_STABLE_VISIT' })}
      />
    );

    expect(
      (screen.getByRole('combobox', { name: 'Visit Stable' }) as HTMLSelectElement).value
    ).toBe('NOT_STABLE_VISIT');
    expect(screen.getByRole('option', { name: 'No', selected: true })).toBeTruthy();
  });

  it('keeps enum values in draft-save and submit payloads', async () => {
    const onSaveDraft = vi.fn().mockResolvedValue(undefined);
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();
    render(
      <ProviderForm
        invitation={invitationConfig({}, onSaveDraft, onSubmit)}
      />
    );

    const select = screen.getByRole('combobox', { name: 'Visit Stable' });
    await user.selectOptions(select, 'NOT_STABLE_VISIT');
    await user.click(screen.getByRole('button', { name: 'Save draft' }));
    await waitFor(() => expect(onSaveDraft).toHaveBeenCalledWith(
      expect.objectContaining({ visit_stability: 'NOT_STABLE_VISIT' })
    ));

    await user.selectOptions(select, 'STABLE_VISIT');
    await user.click(screen.getByRole('button', { name: 'Submit for review' }));
    await waitFor(() => expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({ visit_stability: 'STABLE_VISIT' })
    ));
  });

  it('uses a checkbox instead of a select for stable visits in administrator mode', async () => {
    render(<ProviderForm />);
    const user = await beginAdminWizard();
    const checkbox = screen.getByRole('checkbox', { name: /Stable visit/ }) as HTMLInputElement;
    expect(checkbox.checked).toBe(false);
    expect(screen.queryByLabelText('Clinic / hospital visits')).toBeNull();
    expect(screen.queryByLabelText('Emergency contact name')).toBeNull();
    expect(screen.getByRole('combobox', { name: 'Status' }).parentElement?.parentElement?.contains(
      screen.getByRole('combobox', { name: 'Publication status' })
    )).toBe(true);
    await user.click(checkbox);
    expect(checkbox.checked).toBe(true);
  });

  it('does not render admin-only controls in invitation mode', () => {
    render(<ProviderForm invitation={invitationConfig()} />);
    expect(screen.queryByLabelText('First name')).toBeNull();
    expect(screen.queryByLabelText('Last name')).toBeNull();
    expect(screen.queryByText('Languages')).toBeNull();
    expect(screen.queryByLabelText('Profile photo')).toBeNull();
    expect(screen.queryByText('Clinic / hospital visits')).toBeNull();
  });

  it('shows and requires a positive radius only for stable administrator visits', async () => {
    render(<ProviderForm />);
    const user = await beginAdminWizard();
    const visit = screen.getByRole('checkbox', { name: /Stable visit/ });
    await user.click(visit);
    const radius = screen.getByLabelText('Maximum working radius (km)') as HTMLInputElement;
    expect(visit.closest('div')?.contains(radius)).toBe(true);
    expect(radius.required).toBe(true);
    expect(radius.min).toBe('0.01');
    await user.click(visit);
    expect(screen.queryByLabelText('Maximum working radius (km)')).toBeNull();
  });

  it('blocks a new admin provider when email, location, and stable radius are missing', async () => {
    render(<ProviderForm />);
    const user = await beginAdminWizard();
    await user.click(screen.getByRole('checkbox', { name: /Stable visit/ }));
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    expect(createProvider).not.toHaveBeenCalled();
    expect(screen.getByText('A finite radius greater than 0 is required for stable visits.')).toBeTruthy();
    await user.type(screen.getByLabelText('Maximum working radius (km)'), '15');
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    expect(screen.getByText('A primary email is required.')).toBeTruthy();
    expect(screen.getByText('Country is required.')).toBeTruthy();
    expect(screen.getByText('City is required.')).toBeTruthy();
    expect(screen.getByText('Address is required.')).toBeTruthy();
    expect(screen.getByText('Pincode / postal code is required.')).toBeTruthy();
  });

  it('shows emergency contact fields beside the emergency checkbox and requires the number', async () => {
    render(<ProviderForm />);
    const user = await beginAdminWizard();
    expect(screen.queryByLabelText('Emergency contact name')).toBeNull();
    const emergency = screen.getByRole('checkbox', { name: /Emergency services available/ });
    await user.click(emergency);
    const number = screen.getByLabelText('Emergency contact number') as HTMLInputElement;
    expect(emergency.closest('div')?.contains(number)).toBe(true);
    expect(number.required).toBe(true);
    expect(screen.queryByLabelText('Emergency contact name')).toBeNull();
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    expect(screen.getByText('Emergency contact number is required.')).toBeTruthy();
    await user.type(number, '+91 9988776655');
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    expect(screen.getByLabelText('Pincode / postal code')).toBeTruthy();
  });

  it('creates an emergency provider with only a contact number', async () => {
    vi.mocked(createProvider).mockResolvedValue({ id: 'emergency-provider', photos: [] } as unknown as Provider);
    render(<ProviderForm />);
    const user = await beginAdminWizard();
    await user.click(screen.getByRole('checkbox', { name: /Emergency services available/ }));
    await user.type(screen.getByLabelText('Emergency contact number'), '+91 9988776655');
    await finishClinicWizard(user);
    expect(screen.queryByText('Clinic / hospital visits')).toBeNull();
    expect(screen.queryByText('Emergency contact name')).toBeNull();
    expect(screen.getByText('+91 9988776655')).toBeTruthy();
    await waitFor(() => expect(screen.getByRole('button', { name: 'Create provider' }).hasAttribute('disabled')).toBe(false));
    await user.click(screen.getByRole('button', { name: 'Create provider' }));
    await waitFor(() => expect(createProvider).toHaveBeenCalledWith(expect.objectContaining({
      emergency_services_available: true,
      emergency_contact_number: '+91 9988776655',
    })));
    const body = vi.mocked(createProvider).mock.calls[0][0];
    expect(body).not.toHaveProperty('clinic_hospital_visit');
    expect(body).not.toHaveProperty('emergency_contact_name');
  });

  it('renders the language master option and selection control for admin forms', async () => {
    render(<ProviderForm />);
    const user = userEvent.setup();
    await waitFor(() => expect(screen.getByRole('button', { name: 'Languages' }).hasAttribute('disabled')).toBe(false));
    await user.click(screen.getByRole('button', { name: 'Languages' }));
    expect(screen.getByLabelText('Search languages')).toBeTruthy();
    expect(screen.getByRole('option', { name: /English/ })).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Remove English' })).toBeNull();
  });

  it('saves filtered bulk selections and individual changes from both admin pickers', async () => {
    vi.mocked(createProvider).mockResolvedValue({ id: 'bulk-provider', photos: [] } as unknown as Provider);
    vi.mocked(listSpecializations).mockResolvedValueOnce({
      data: [
        { id: 'spec-a', name: 'Dental care', is_active: true },
        { id: 'spec-b', name: 'Dental surgery', is_active: true },
        { id: 'spec-c', name: 'Emergency care', is_active: true },
      ],
      meta: { page: 1, page_size: 100, total: 3, total_pages: 1 },
    } as never);
    vi.mocked(listLanguages).mockResolvedValueOnce({
      data: [
        { id: 'lang-en', name: 'English', code: 'en', is_active: true },
        { id: 'lang-fr', name: 'French', code: 'fr', is_active: true },
        { id: 'lang-de', name: 'German', code: 'de', is_active: true },
      ],
      meta: { page: 1, page_size: 100, total: 3, total_pages: 1 },
    } as never);
    const user = userEvent.setup();
    render(<ProviderForm />);
    const specs = await screen.findByRole('button', { name: 'Specializations' });
    await waitFor(() => expect(specs.hasAttribute('disabled')).toBe(false));
    await user.click(specs);
    const specSearch = screen.getByRole('searchbox', { name: 'Search specializations' });
    await user.type(specSearch, 'Dental');
    await user.click(screen.getByRole('button', { name: 'Select all' }));
    expect(specs.textContent).toContain('2 selected');
    await user.clear(specSearch);
    await user.click(screen.getByRole('option', { name: 'Emergency care' }));
    await user.type(specSearch, 'Dental');
    await user.click(screen.getByRole('button', { name: 'Clear all' }));
    expect(specs.textContent).toContain('1 selected');
    await user.clear(specSearch);
    await user.click(screen.getByRole('option', { name: 'Dental care' }));
    await user.click(specs);

    const langs = screen.getByRole('button', { name: 'Languages' });
    await user.click(langs);
    const langSearch = screen.getByRole('searchbox', { name: 'Search languages' });
    await user.type(langSearch, 'en');
    await user.click(screen.getByRole('button', { name: 'Select all' }));
    expect(langs.textContent).toContain('2 selected');
    await user.clear(langSearch);
    await user.click(screen.getByRole('option', { name: /German/ }));
    await user.type(langSearch, 'en');
    await user.click(screen.getByRole('button', { name: 'Clear all' }));
    expect(langs.textContent).toContain('1 selected');
    await user.click(screen.getByRole('option', { name: /English/ }));
    await user.click(langs);

    await user.selectOptions(screen.getByRole('combobox', { name: 'Provider type' }), 'CLINIC');
    await user.type(screen.getByLabelText('Provider / practice name'), 'North Star');
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    await finishClinicWizard(user);
    await waitFor(() => expect(screen.getByRole('button', { name: 'Create provider' }).hasAttribute('disabled')).toBe(false));
    await user.click(screen.getByRole('button', { name: 'Create provider' }));
    await waitFor(() => expect(createProvider).toHaveBeenCalledWith(expect.objectContaining({
      specialization_ids: ['spec-c', 'spec-a'],
      language_ids: ['lang-de', 'lang-en'],
    })));
  });

  it('fills location from an explicitly chosen postal match and permits manual correction', async () => {
    vi.mocked(lookupProviderPostalCode).mockResolvedValueOnce({
      status: 'match',
      candidates: [{
        postal_code: '110001', country: 'India', country_code: 'IN',
        state_province: 'Delhi', city: 'New Delhi', display_name: 'New Delhi, Delhi, India',
      }],
    });
    render(<ProviderForm />);
    const user = await beginAdminWizard();
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    const postal = screen.getByLabelText('Pincode / postal code');
    await user.type(postal, '110001');
    const candidate = await screen.findByRole('button', { name: 'New Delhi, Delhi, India' });
    expect(lookupProviderPostalCode).toHaveBeenCalledWith('110001', expect.any(AbortSignal));
    expect(screen.getByRole('button', { name: 'Country' }).textContent).toContain('Select country');
    await user.click(candidate);
    expect(screen.getByRole('button', { name: 'Country' }).textContent).toContain('India');
    expect(screen.getByRole('button', { name: 'State / Province' }).textContent).toContain('Delhi');
    expect(screen.getByRole('button', { name: 'City' }).textContent).toContain('New Delhi');
    await user.clear(postal);
    await user.type(postal, 'othercode');
    expect(screen.getByRole('button', { name: 'Country' }).textContent).toContain('Select country');
    expect(screen.getByRole('button', { name: 'Country' }).hasAttribute('disabled')).toBe(false);
  });

  it('checks doctor names and qualification titles before leaving professional details', async () => {
    render(<ProviderForm />);
    const user = await beginAdminWizard('DOCTOR');
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    expect(screen.getByText('First name is required.')).toBeTruthy();
    expect(screen.getByText('Last name is required.')).toBeTruthy();
    await user.type(screen.getByLabelText('First name'), 'Amina');
    await user.type(screen.getByLabelText('Last name'), 'Khan');
    await user.click(screen.getByRole('button', { name: 'Add qualification' }));
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    expect(screen.getByText('Qualification title is required.')).toBeTruthy();
    await user.type(screen.getByLabelText('Title'), 'DVM');
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    expect(screen.getByRole('checkbox', { name: /Stable visit/ })).toBeTruthy();
  });

  it('keeps entries when moving back, reviews them, and creates only after confirmation', async () => {
    const onSuccess = vi.fn();
    const saved = { id: 'provider-1', photos: [] } as unknown as Provider;
    vi.mocked(createProvider).mockResolvedValue(saved);
    vi.mocked(listSpecializations).mockResolvedValueOnce({
      data: [{ id: 'spec-emergency', name: 'Emergency care', is_active: true }],
      meta: { page: 1, page_size: 100, total: 1, total_pages: 1 },
    } as never);
    render(<MemoryRouter initialEntries={['/admin/providers/new']}><ProviderForm onSuccess={onSuccess} /><CurrentPath /></MemoryRouter>);
    const picker = userEvent.setup();
    await picker.click(screen.getByRole('button', { name: 'Languages' }));
    await picker.type(screen.getByLabelText('Search languages'), 'Eng');
    await picker.click(screen.getByRole('option', { name: /English/ }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Specializations' }).hasAttribute('disabled')).toBe(false));
    await picker.click(screen.getByRole('button', { name: 'Specializations' }));
    await picker.type(screen.getByLabelText('Search specializations'), 'Emer');
    await picker.click(screen.getByRole('option', { name: 'Emergency care' }));
    const user = await beginAdminWizard();
    await finishClinicWizard(user);

    expect(createProvider).not.toHaveBeenCalled();
    expect(onSuccess).not.toHaveBeenCalled();
    expect(screen.getByLabelText('Current path').textContent).toBe('/admin/providers/new');
    expect(screen.getByText('clinic@example.com')).toBeTruthy();
    expect(screen.queryByText('Clinic / hospital visits')).toBeNull();
    expect(screen.queryByText('Emergency contact name')).toBeNull();
    expect(screen.getByText('42 Stable Road, Calgary, Alberta, Canada')).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'Back' }));
    expect((screen.getByRole('textbox', { name: 'Email address 1' }) as HTMLInputElement).value).toBe('clinic@example.com');
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    await user.click(screen.getByRole('button', { name: 'Edit Contact & location' }));
    expect((screen.getByRole('textbox', { name: 'Email address 1' }) as HTMLInputElement).value).toBe('clinic@example.com');
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Create provider' }).hasAttribute('disabled')).toBe(false));
    await user.click(screen.getByRole('button', { name: 'Create provider' }));

    await waitFor(() => expect(onSuccess).toHaveBeenCalledWith(saved));
    expect(createProvider).toHaveBeenCalledTimes(1);
    expect(createProvider).toHaveBeenCalledWith(expect.objectContaining({
      name: 'North Star',
      provider_type: 'CLINIC',
      admin_form_version: 2,
      language_ids: ['lang-en'],
      specialization_ids: ['spec-emergency'],
      primary_location: expect.objectContaining({ country: 'Canada', city: 'Calgary' }),
      emails: [expect.objectContaining({ email: 'clinic@example.com', is_primary: true })],
    }));
    expect(vi.mocked(createProvider).mock.calls[0][0]).not.toHaveProperty('clinic_hospital_visit');
    expect(vi.mocked(createProvider).mock.calls[0][0]).not.toHaveProperty('emergency_contact_name');
  });

  it('ignores implicit submits and rapid repeat clicks across the review transition', async () => {
    let resolveCreate!: (saved: Provider) => void;
    vi.mocked(createProvider).mockImplementation(() => new Promise((resolve) => { resolveCreate = resolve; }));
    const onSuccess = vi.fn();
    render(<ProviderForm onSuccess={onSuccess} />);
    const user = await beginAdminWizard();
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    await user.click(screen.getByRole('button', { name: /Add email/i }));
    await user.type(screen.getByRole('textbox', { name: 'Email address 1' }), 'clinic@example.com');
    await user.type(screen.getByLabelText('Address line 1'), '42 Stable Road');
    await user.type(screen.getByLabelText('Pincode / postal code'), 'T2P 1J9');
    await user.click(screen.getByRole('button', { name: 'Country' }));
    await user.type(screen.getByRole('combobox', { name: 'Search country' }), 'Canada');
    await user.click(screen.getByRole('option', { name: 'Canada' }));
    await user.click(screen.getByRole('button', { name: 'State / Province' }));
    await user.type(screen.getByRole('combobox', { name: 'Search state / province' }), 'Alberta');
    await user.click(screen.getByRole('option', { name: 'Alberta' }));
    await user.click(screen.getByRole('button', { name: 'City' }));
    await user.type(screen.getByRole('combobox', { name: 'Search city' }), 'Calgary');
    await user.click(screen.getByRole('option', { name: 'Calgary' }));

    const form = screen.getByRole('button', { name: 'Continue' }).closest('form')!;
    fireEvent.submit(form); // Enter in a field must not skip review.
    expect(screen.getByRole('heading', { name: 'Contact & location' })).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    expect(screen.getByRole('heading', { name: 'Review & create' })).toBeTruthy();
    expect(createProvider).not.toHaveBeenCalled();
    fireEvent.submit(form); // No implicit submit on review either.
    expect(createProvider).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: 'Create provider' }).hasAttribute('disabled')).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: 'Create provider' }));
    expect(createProvider).not.toHaveBeenCalled();

    await waitFor(() => expect(screen.getByRole('button', { name: 'Create provider' }).hasAttribute('disabled')).toBe(false));
    const createButton = screen.getByRole('button', { name: 'Create provider' });
    createButton.focus();
    await user.keyboard('{Enter}');
    fireEvent.click(createButton);
    expect(createProvider).toHaveBeenCalledTimes(1);
    resolveCreate({ id: 'provider-once', photos: [] } as unknown as Provider);
    await waitFor(() => expect(onSuccess).toHaveBeenCalledTimes(1));
  });

  it('retries a failed photo upload without creating a second provider', async () => {
    Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: vi.fn(() => 'blob:photo') });
    const saved = { id: 'provider-photo', photos: [] } as unknown as Provider;
    const onSuccess = vi.fn();
    vi.mocked(createProvider).mockResolvedValue(saved);
    vi.mocked(uploadProviderPhoto).mockRejectedValueOnce(new Error('upload unavailable')).mockResolvedValueOnce({} as never);
    vi.mocked(getProvider).mockResolvedValue(saved);
    render(<MemoryRouter><ProviderForm onSuccess={onSuccess} /></MemoryRouter>);
    const user = userEvent.setup();
    await user.selectOptions(screen.getByRole('combobox', { name: 'Provider type' }), 'CLINIC');
    await user.type(screen.getByLabelText('Provider / practice name'), 'North Star');
    await user.upload(screen.getByLabelText(/Profile photo/), new File(['image'], 'provider.png', { type: 'image/png' }));
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    await finishClinicWizard(user);
    await waitFor(() => expect(screen.getByRole('button', { name: 'Create provider' }).hasAttribute('disabled')).toBe(false));
    await user.click(screen.getByRole('button', { name: 'Create provider' }));
    await waitFor(() => expect(screen.getByText(/Provider saved, but the photo could not be uploaded/)).toBeTruthy());
    expect(createProvider).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('button', { name: 'Edit Contact & location' }).hasAttribute('disabled')).toBe(true);
    await user.click(screen.getAllByRole('button', { name: 'Retry photo upload' })[0]);
    await waitFor(() => expect(onSuccess).toHaveBeenCalledWith(saved));
    expect(createProvider).toHaveBeenCalledTimes(1);
    expect(uploadProviderPhoto).toHaveBeenCalledTimes(2);
  });

  it('previews a new photo on create review and keeps the empty photo state when none is selected', async () => {
    const user = userEvent.setup();
    render(<ProviderForm />);
    await beginAdminWizard();
    await finishClinicWizard(user);
    expect(screen.getByText('No photo selected')).toBeTruthy();
    expect(screen.queryByRole('img', { name: /profile photo/i })).toBeNull();
    expect(createProvider).not.toHaveBeenCalled();

    await user.click(screen.getByRole('button', { name: 'Edit Basic details' }));
    const objectUrl = vi.fn(() => 'blob:selected-photo');
    Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: objectUrl });
    const file = new File(['image'], 'new-profile.png', { type: 'image/png' });
    await user.upload(screen.getByLabelText(/Profile photo/), file);
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    const preview = screen.getByRole('img', { name: 'Selected profile photo: new-profile.png' }) as HTMLImageElement;
    expect(preview.src).toContain('blob:selected-photo');
    expect(createProvider).not.toHaveBeenCalled();
  });

  it('shows new doctor qualifications with complete and partial details before creation', async () => {
    render(<ProviderForm />);
    const user = await beginAdminWizard('DOCTOR');
    await user.type(screen.getByLabelText('First name'), 'Amina');
    await user.type(screen.getByLabelText('Last name'), 'Khan');
    await user.click(screen.getByRole('button', { name: 'Add qualification' }));
    await user.type(screen.getByLabelText('Title'), 'DVM');
    await user.type(screen.getByLabelText('Institution'), 'Western College');
    await user.type(screen.getByLabelText('Year'), '2018');
    await user.click(screen.getByRole('button', { name: 'Add qualification' }));
    await user.type(screen.getAllByLabelText('Title')[1], 'Fellowship');
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    await finishClinicWizard(user);
    const list = screen.getByText('DVM').closest('ul')!;
    expect(list.children).toHaveLength(2);
    expect(list.children[0].textContent).toBe('DVMWestern College · 2018');
    expect(list.children[1].textContent).toBe('Fellowship');
    expect(createProvider).not.toHaveBeenCalled();
  });
});

describe('ProviderForm edit wizard', () => {
  it('keeps legacy emergency edits valid when the saved number is missing', async () => {
    const provider = existingProvider({ emergency_contact_number: null });
    vi.mocked(updateProvider).mockResolvedValue(provider);
    vi.mocked(getProvider).mockResolvedValue(provider);
    render(<ProviderForm initialData={provider} />);
    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    const number = screen.getByLabelText('Emergency contact number') as HTMLInputElement;
    expect(number.required).toBe(false);
    expect(screen.queryByLabelText('Emergency contact name')).toBeNull();
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    expect(screen.getByRole('heading', { name: 'Contact & location' })).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Save changes' }).hasAttribute('disabled')).toBe(false));
    await user.click(screen.getByRole('button', { name: 'Save changes' }));
    await waitFor(() => expect(updateProvider).toHaveBeenCalledTimes(1));
    expect(vi.mocked(updateProvider).mock.calls[0][1]).not.toHaveProperty('emergency_contact_name');
    expect(vi.mocked(updateProvider).mock.calls[0][1]).not.toHaveProperty('emergency_contact_number');
  });

  it('requires a number when emergency service is newly enabled on edit', async () => {
    const provider = existingProvider({ emergency_services_available: false, emergency_contact_number: null });
    render(<ProviderForm initialData={provider} />);
    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    await user.click(screen.getByRole('checkbox', { name: /Emergency services available/ }));
    expect((screen.getByLabelText('Emergency contact number') as HTMLInputElement).required).toBe(true);
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    expect(screen.getByText('Emergency contact number is required.')).toBeTruthy();
  });

  it('shows the existing thumbnail, then previews the replacement on review without saving early', async () => {
    const provider = existingProvider({ thumbnail_url: '/uploads/original.png' });
    render(<ProviderForm initialData={provider} />);
    const user = userEvent.setup();
    await reachEditReview(user);
    expect((screen.getByRole('img', { name: 'Current provider profile photo' }) as HTMLImageElement).getAttribute('src')).toBe('/uploads/original.png');
    await user.click(screen.getByRole('button', { name: 'Edit Basic details' }));
    Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: vi.fn(() => 'blob:replacement') });
    await user.upload(screen.getByLabelText(/Profile photo/), new File(['photo'], 'replacement.webp', { type: 'image/webp' }));
    await reachEditReview(user);
    expect((screen.getByRole('img', { name: 'Selected profile photo: replacement.webp' }) as HTMLImageElement).src).toContain('blob:replacement');
    expect(updateProvider).not.toHaveBeenCalled();
    expect(uploadProviderPhoto).not.toHaveBeenCalled();
  });

  it('reviews multiple doctor qualifications with optional details separately', async () => {
    const provider = existingProvider({
      provider_type: 'DOCTOR',
      qualifications: [
        { id: 'q1', title: 'DVM', institution: 'Western College', year_obtained: 2017, description: null, display_order: 0 },
        { id: 'q2', title: 'Fellowship', institution: null, year_obtained: 2022, description: null, display_order: 1 },
        { id: 'q3', title: 'Certification', institution: 'Equine Institute', year_obtained: null, description: null, display_order: 2 },
      ] as Provider['qualifications'],
    });
    render(<ProviderForm initialData={provider} />);
    await reachEditReview(userEvent.setup(), true);
    const list = screen.getByText('DVM').closest('ul')!;
    expect(list.children).toHaveLength(3);
    expect(list.children[0].textContent).toBe('DVMWestern College · 2017');
    expect(list.children[1].textContent).toBe('Fellowship2022');
    expect(list.children[2].textContent).toBe('CertificationEquine Institute');
    expect(updateProvider).not.toHaveBeenCalled();
  });

  it('prepopulates steps and review, preserves Back/Edit changes, and saves only after confirmation', async () => {
    const provider = existingProvider();
    const onSuccess = vi.fn();
    vi.mocked(updateProvider).mockResolvedValue(provider);
    vi.mocked(getProvider).mockResolvedValue(provider);
    render(<ProviderForm initialData={provider} onSuccess={onSuccess} />);
    const user = userEvent.setup();
    expect(screen.getByText(/EDIT PROVIDER · STEP 1 OF 4/)).toBeTruthy();
    expect((screen.getByLabelText('Provider / practice name') as HTMLInputElement).value).toBe('Cedar Ridge');
    expect(await screen.findByRole('button', { name: 'Remove Old specialty' })).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    expect(screen.queryByRole('checkbox', { name: /Clinic \/ hospital visits/ })).toBeNull();
    expect(screen.queryByLabelText('Emergency contact name')).toBeNull();
    expect((screen.getByLabelText('Emergency contact number') as HTMLInputElement).value).toBe('+1 403 555 9999');
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    expect((screen.getByLabelText('Location name') as HTMLInputElement).value).toBe('Main branch');
    expect((screen.getByLabelText('Pincode / postal code') as HTMLInputElement).value).toBe('T2P 1J9');
    expect((screen.getByRole('textbox', { name: 'Email address 1' }) as HTMLInputElement).value).toBe('old@example.com');
    await user.clear(screen.getByRole('textbox', { name: 'Email address 1' }));
    await user.type(screen.getByRole('textbox', { name: 'Email address 1' }), 'new@example.com');
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    expect(updateProvider).not.toHaveBeenCalled();
    expect(screen.getByText('new@example.com')).toBeTruthy();
    expect(screen.getByText('Main branch')).toBeTruthy();
    expect(screen.queryByText('Clinic / hospital visits')).toBeNull();
    expect(screen.queryByText('Emergency contact name')).toBeNull();
    await user.click(screen.getByRole('button', { name: 'Back' }));
    expect((screen.getByRole('textbox', { name: 'Email address 1' }) as HTMLInputElement).value).toBe('new@example.com');
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    await user.click(screen.getByRole('button', { name: 'Edit Services' }));
    expect(screen.queryByLabelText('Emergency contact name')).toBeNull();
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    const form = screen.getByRole('button', { name: 'Save changes' }).closest('form')!;
    fireEvent.submit(form);
    expect(updateProvider).not.toHaveBeenCalled();
    await waitFor(() => expect(screen.getByRole('button', { name: 'Save changes' }).hasAttribute('disabled')).toBe(false));
    fireEvent.click(screen.getByRole('button', { name: 'Save changes' }));
    fireEvent.click(screen.getByRole('button', { name: 'Save changes' }));
    await waitFor(() => expect(onSuccess).toHaveBeenCalledTimes(1));
    expect(updateProvider).toHaveBeenCalledTimes(1);
    const editBody = vi.mocked(updateProvider).mock.calls[0][1];
    expect(editBody).not.toHaveProperty('clinic_hospital_visit');
    expect(editBody).not.toHaveProperty('emergency_contact_name');
    expect(editBody).not.toHaveProperty('emergency_services_available');
    expect(editBody).not.toHaveProperty('emergency_contact_number');
    expect(removeProviderEmail).toHaveBeenCalledWith('provider-1', 'email-1');
    expect(addProviderEmail).toHaveBeenCalledWith('provider-1', expect.objectContaining({ email: 'new@example.com' }));
    expect(updateProviderLocation).not.toHaveBeenCalled();
  });

  it('allows unrelated changes to legacy incomplete records without adding missing required fields', async () => {
    const provider = existingProvider({
      provider_type: 'DOCTOR', doctor_profile: null, emails: [], locations: [],
      specializations: [], languages: [], phones: [], emergency_services_available: false,
    });
    vi.mocked(updateProvider).mockResolvedValue(provider);
    vi.mocked(getProvider).mockResolvedValue(provider);
    const user = userEvent.setup();
    render(<ProviderForm initialData={provider} />);
    await user.clear(screen.getByLabelText('Provider / practice name'));
    await user.type(screen.getByLabelText('Provider / practice name'), 'Updated practice');
    await reachEditReview(user, true);
    expect(screen.getByText('Updated practice')).toBeTruthy();
    await waitFor(() => expect(screen.getByRole('button', { name: 'Save changes' }).hasAttribute('disabled')).toBe(false));
    await user.click(screen.getByRole('button', { name: 'Save changes' }));
    await waitFor(() => expect(updateProvider).toHaveBeenCalledTimes(1));
    expect(updateProvider).toHaveBeenCalledWith('provider-1', expect.objectContaining({ name: 'Updated practice' }));
    expect(updateProviderLocation).not.toHaveBeenCalled();
  });

  it('explains newly missing doctor names on the professional step', async () => {
    const provider = existingProvider({
      provider_type: 'DOCTOR',
      doctor_profile: {
        first_name: 'Amina', last_name: 'Khan', professional_title: null,
        biography: null, years_experience: null, experience_description: null,
      },
    });
    const user = userEvent.setup();
    render(<ProviderForm initialData={provider} />);
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    await user.clear(screen.getByLabelText('First name'));
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    expect(screen.getByText('First name is required.')).toBeTruthy();
    expect(screen.getByRole('heading', { name: 'Professional details' })).toBeTruthy();
    expect(updateProvider).not.toHaveBeenCalled();
  });

  it('keeps type transitions coherent and sends changed relationships, services and location', async () => {
    const provider = existingProvider();
    vi.mocked(updateProvider).mockResolvedValue(provider);
    vi.mocked(getProvider).mockResolvedValue(provider);
    const user = userEvent.setup();
    render(<ProviderForm initialData={provider} />);
    await user.selectOptions(screen.getByRole('combobox', { name: 'Provider type' }), 'DOCTOR');
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    expect(screen.getByRole('heading', { name: 'Professional details' })).toBeTruthy();
    await user.type(screen.getByLabelText('First name'), 'Amina');
    await user.click(screen.getByRole('button', { name: 'Back' }));
    await user.selectOptions(screen.getByRole('combobox', { name: 'Provider type' }), 'HOSPITAL');
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    expect(screen.getByRole('heading', { name: 'Services' })).toBeTruthy();
    await user.selectOptions(screen.getByRole('combobox', { name: 'Status' }), 'INACTIVE');
    await user.selectOptions(screen.getByRole('combobox', { name: 'Publication status' }), 'PUBLISHED');
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    await user.clear(screen.getByLabelText('Location name'));
    await user.type(screen.getByLabelText('Location name'), 'West wing');
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Save changes' }).hasAttribute('disabled')).toBe(false));
    await user.click(screen.getByRole('button', { name: 'Save changes' }));
    await waitFor(() => expect(updateProviderLocation).toHaveBeenCalled());
    expect(updateProvider).toHaveBeenCalledWith('provider-1', expect.objectContaining({
      provider_type: 'HOSPITAL',
    }));
    expect(vi.mocked(updateProvider).mock.calls[0][1]).not.toHaveProperty('clinic_hospital_visit');
    expect(vi.mocked(updateProvider).mock.calls[0][1]).not.toHaveProperty('emergency_contact_name');
    expect(updateProviderStatus).toHaveBeenCalledWith('provider-1', 'INACTIVE');
    expect(updateProviderPublication).toHaveBeenCalledWith('provider-1', 'PUBLISHED');
    expect(updateProviderLocation).toHaveBeenCalledWith('provider-1', 'location-1', expect.objectContaining({ name: 'West wing' }));
    expect(addProviderPhone).not.toHaveBeenCalled();
    expect(removeProviderPhone).not.toHaveBeenCalled();
    expect(addProviderSpecialization).not.toHaveBeenCalled();
    expect(removeProviderSpecialization).not.toHaveBeenCalled();
  });

  it('saves edited selectors, phone, postal correction and photo on the existing provider', async () => {
    const provider = existingProvider();
    vi.mocked(listSpecializations).mockResolvedValueOnce({
      data: [{ id: 'spec-2', name: 'Equine care', is_active: true }],
      meta: { page: 1, page_size: 100, total: 1, total_pages: 1 },
    } as never);
    vi.mocked(lookupProviderPostalCode).mockResolvedValueOnce({
      status: 'match', candidates: [{
        postal_code: '110001', country: 'India', country_code: 'IN',
        state_province: 'Delhi', city: 'New Delhi', display_name: 'New Delhi, Delhi, India',
      }],
    });
    Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: vi.fn(() => 'blob:edit-photo') });
    vi.mocked(updateProvider).mockResolvedValue(provider);
    vi.mocked(getProvider).mockResolvedValue(provider);
    vi.mocked(uploadProviderPhoto).mockResolvedValue({ id: 'photo-2' } as never);
    const user = userEvent.setup();
    const onSuccess = vi.fn();
    render(<ProviderForm initialData={provider} onSuccess={onSuccess} />);
    await waitFor(() => expect(screen.getByRole('button', { name: 'Specializations' }).hasAttribute('disabled')).toBe(false));
    await user.click(screen.getByRole('button', { name: 'Remove Old specialty' }));
    await user.click(screen.getByRole('button', { name: 'Specializations' }));
    await user.click(screen.getByRole('option', { name: 'Equine care' }));
    await user.click(screen.getByRole('button', { name: 'Remove English' }));
    await user.upload(screen.getByLabelText(/Profile photo/), new File(['image'], 'new.png', { type: 'image/png' }));
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    await user.clear(screen.getByRole('textbox', { name: 'Phone number 1' }));
    await user.type(screen.getByRole('textbox', { name: 'Phone number 1' }), '4035550200');
    const postal = screen.getByLabelText('Pincode / postal code');
    await user.clear(postal);
    await user.type(postal, '110001');
    await user.click(await screen.findByRole('button', { name: 'New Delhi, Delhi, India' }));
    await user.click(screen.getByRole('button', { name: 'City' }));
    await user.type(screen.getByRole('combobox', { name: 'Search city' }), 'Delhi');
    await user.click(screen.getByRole('option', { name: 'New Delhi' }));
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    expect(updateProvider).not.toHaveBeenCalled();
    await waitFor(() => expect(screen.getByRole('button', { name: 'Save changes' }).hasAttribute('disabled')).toBe(false));
    await user.click(screen.getByRole('button', { name: 'Save changes' }));
    await waitFor(() => expect(onSuccess).toHaveBeenCalledTimes(1));
    expect(updateProvider).toHaveBeenCalledWith('provider-1', expect.objectContaining({ language_ids: [] }));
    expect(removeProviderSpecialization).toHaveBeenCalledWith('provider-1', 'spec-1');
    expect(addProviderSpecialization).toHaveBeenCalledWith('provider-1', 'spec-2');
    expect(removeProviderPhone).toHaveBeenCalledWith('provider-1', 'phone-1');
    expect(addProviderPhone).toHaveBeenCalledWith('provider-1', expect.objectContaining({ number: '4035550200' }));
    expect(updateProviderLocation).toHaveBeenCalledWith('provider-1', 'location-1', expect.objectContaining({
      postal_code: '110001', city: 'New Delhi',
    }));
    expect(uploadProviderPhoto).toHaveBeenCalledWith('provider-1', expect.any(File), expect.objectContaining({ is_thumbnail: true }));
  });
});