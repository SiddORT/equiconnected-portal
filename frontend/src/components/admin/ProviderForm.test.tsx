import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { ProviderForm, type InvitationFormConfig } from './ProviderForm';
import type { InvitationDraftProvider, Provider } from '@/types';
import { createProvider, getProvider, uploadProviderPhoto } from '@/api/providers';
import { lookupProviderPostalCode } from '@/api/auth';
import { listSpecializations } from '@/api/specializations';

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

  it('shows only the emergency contact number beside the emergency checkbox and requires it', async () => {
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
    await user.click(screen.getByRole('button', { name: 'Create provider' }));
    await waitFor(() => expect(createProvider).toHaveBeenCalledWith(expect.objectContaining({
      emergency_services_available: true,
      emergency_contact_number: '+91 9988776655',
      emergency_contact_name: null,
    })));
  });

  it('renders the language master option and selection control for admin forms', async () => {
    render(<ProviderForm />);
    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'Languages' }));
    expect(screen.getByLabelText('Search languages')).toBeTruthy();
    expect(screen.getByRole('option', { name: /English/ })).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Remove English' })).toBeNull();
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
    render(<ProviderForm onSuccess={onSuccess} />);
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
    expect(screen.getByText('clinic@example.com')).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'Edit Contact & location' }));
    expect((screen.getByRole('textbox', { name: 'Email address 1' }) as HTMLInputElement).value).toBe('clinic@example.com');
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    await user.click(screen.getByRole('button', { name: 'Create provider' }));

    await waitFor(() => expect(onSuccess).toHaveBeenCalledWith(saved));
    expect(createProvider).toHaveBeenCalledTimes(1);
    expect(createProvider).toHaveBeenCalledWith(expect.objectContaining({
      name: 'North Star',
      provider_type: 'CLINIC',
      admin_form_version: 2,
      language_ids: ['lang-en'],
      specialization_ids: ['spec-emergency'],
      clinic_hospital_visit: false,
      primary_location: expect.objectContaining({ country: 'Canada', city: 'Calgary' }),
      emails: [expect.objectContaining({ email: 'clinic@example.com', is_primary: true })],
    }));
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
    await user.click(screen.getByRole('button', { name: 'Create provider' }));
    await waitFor(() => expect(screen.getByText(/Provider saved, but the photo could not be uploaded/)).toBeTruthy());
    expect(createProvider).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('button', { name: 'Edit Contact & location' }).hasAttribute('disabled')).toBe(true);
    await user.click(screen.getAllByRole('button', { name: 'Retry photo upload' })[0]);
    await waitFor(() => expect(onSuccess).toHaveBeenCalledWith(saved));
    expect(createProvider).toHaveBeenCalledTimes(1);
    expect(uploadProviderPhoto).toHaveBeenCalledTimes(2);
  });
});