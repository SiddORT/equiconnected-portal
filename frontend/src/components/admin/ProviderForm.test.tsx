import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { ProviderForm, type InvitationFormConfig } from './ProviderForm';
import type { InvitationDraftProvider, Provider } from '@/types';
import {
  addProviderEmail, addProviderPhone, addProviderSpecialization, createProvider,
  getProvider, getProviderPortalAccess, removeProviderEmail, removeProviderPhone, removeProviderSpecialization,
  sendProviderPortalAccess,
  updateProvider, updateProviderLocation, updateProviderPublication, updateProviderStatus,
  uploadProviderPhoto,
} from '@/api/providers';
import { listProviderSignupLanguages, lookupProviderPostalCode } from '@/api/auth';
import { listSpecializations } from '@/api/specializations';
import { listLanguages } from '@/api/languages';
import styles from './ProviderForm.module.css';

vi.mock('@/api/providers', () => ({
  addProviderEmail: vi.fn(),
  addProviderPhone: vi.fn(),
  addProviderSpecialization: vi.fn(),
  createProvider: vi.fn(),
  createProviderLocation: vi.fn(),
  getProvider: vi.fn(),
  getProviderPortalAccess: vi.fn(),
  removeProviderEmail: vi.fn(),
  removeProviderPhone: vi.fn(),
  removeProviderSpecialization: vi.fn(),
  sendProviderPortalAccess: vi.fn(),
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
  listProviderSignupLanguages: vi.fn().mockResolvedValue([
    { id: 'lang-en', name: 'English', code: 'en' },
    { id: 'lang-fr', name: 'French', code: 'fr' },
  ]),
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
    recipientEmail: 'invited@example.com',
    emailsEdited: false,
    loadSpecializations: vi.fn().mockResolvedValue([]),
    onSaveDraft,
    onSubmit,
  };
}

async function fillInvitationCredentials(user: ReturnType<typeof userEvent.setup>) {
  const password = screen.getByLabelText('Password') as HTMLInputElement;
  const confirmation = screen.getByLabelText('Confirm password') as HTMLInputElement;
  if (!password.value) await user.type(password, 'SecureHorse7');
  if (!confirmation.value) await user.type(confirmation, 'SecureHorse7');
}

function CurrentPath() {
  return <output aria-label="Current path">{useLocation().pathname}</output>;
}

afterEach(() => { cleanup(); vi.clearAllMocks(); vi.unstubAllGlobals(); });

describe('Admin provider postal lookup', () => {
  beforeEach(() => {
    vi.stubGlobal('matchMedia', () => ({ matches: false }));
    Element.prototype.scrollIntoView = vi.fn();
  });

  async function reachLocationStep(user: ReturnType<typeof userEvent.setup>) {
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    expect(await screen.findByLabelText('Pincode / postal code')).toBeTruthy();
  }

  it('requires explicit selection for a unique match and normalizes the selected country', async () => {
    render(<ProviderForm />);
    const user = await beginAdminWizard();
    vi.mocked(lookupProviderPostalCode).mockResolvedValue({
      status: 'match',
      candidates: [{
        country: 'Unknown',
        country_code: 'in',
        state_province: 'Delhi',
        city: 'New Delhi',
        postal_code: '110001',
        display_name: 'New Delhi, Delhi, India',
      }],
    });
    await reachLocationStep(user);
    await user.type(screen.getByLabelText('Pincode / postal code'), '110001');
    const candidate = await screen.findByRole('button', { name: 'New Delhi, Delhi, India' });
    expect(screen.getByRole('button', { name: 'Country' }).textContent).toContain('Select country');

    await user.click(candidate);
    await user.click(screen.getByRole('button', { name: 'Country' }));
    expect(screen.getByRole('option', { name: 'India' }).getAttribute('aria-selected')).toBe('true');
    await user.keyboard('{Escape}');
    await user.click(screen.getByRole('button', { name: 'State / Province' }));
    expect(screen.getByRole('option', { name: 'Delhi' }).getAttribute('aria-selected')).toBe('true');
    await user.keyboard('{Escape}');
    await user.click(screen.getByRole('button', { name: 'City' }));
    expect(screen.getByRole('option', { name: 'New Delhi' }).getAttribute('aria-selected')).toBe('true');
    expect(screen.getByText('Location filled. You can correct it below.')).toBeTruthy();
  });

  it('cancels stale results after a manual location edit', async () => {
    render(<ProviderForm />);
    const user = await beginAdminWizard();
    let resolveLookup: ((result: {
      status: 'match';
      candidates: Array<{
        country: string; country_code?: string; state_province: string; city: string;
        postal_code: string; display_name: string;
      }>;
    }) => void) | null = null;
    vi.mocked(lookupProviderPostalCode).mockImplementationOnce(() => new Promise((resolve) => {
      resolveLookup = resolve;
    }));
    await reachLocationStep(user);
    await user.type(screen.getByLabelText('Pincode / postal code'), '90210');
    await waitFor(() => expect(lookupProviderPostalCode).toHaveBeenCalled());

    await user.click(screen.getByRole('button', { name: 'Country' }));
    await user.type(screen.getByRole('combobox', { name: 'Search country' }), 'Canada');
    await user.click(screen.getByRole('option', { name: 'Canada' }));
    await act(async () => {
      resolveLookup?.({
        status: 'match',
        candidates: [{
          country: 'United States', country_code: 'US', state_province: 'California',
          city: 'Beverly Hills', postal_code: '90210', display_name: 'Beverly Hills, CA',
        }],
      });
    });
    expect(screen.queryByRole('button', { name: 'Beverly Hills, CA' })).toBeNull();
    expect(screen.queryByText('Choose a place below to fill your location.')).toBeNull();
    expect(screen.queryByText('Looking up locations…')).toBeNull();
    expect(screen.getByRole('button', { name: 'Country' }).textContent).toContain('Canada');
  });

  it('skips short queries and reports lookup failures', async () => {
    render(<ProviderForm />);
    const user = await beginAdminWizard();
    await reachLocationStep(user);
    const postal = screen.getByLabelText('Pincode / postal code');
    await user.type(postal, '123');
    expect(lookupProviderPostalCode).not.toHaveBeenCalled();

    vi.mocked(lookupProviderPostalCode).mockRejectedValueOnce(new Error('offline'));
    await user.type(postal, '4');
    expect(await screen.findByText('Lookup is unavailable. Enter the location manually.')).toBeTruthy();
  });
});

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

describe('Admin emergency country picker', () => {
  beforeEach(() => {
    vi.stubGlobal('matchMedia', () => ({ matches: false }));
    Element.prototype.scrollIntoView = vi.fn();
    vi.mocked(createProvider).mockResolvedValue({ id: 'new-provider', photos: [] } as unknown as Provider);
    vi.mocked(updateProvider).mockResolvedValue(existingProvider());
    vi.mocked(getProvider).mockResolvedValue(existingProvider());
  });

  async function saveEdit(user: ReturnType<typeof userEvent.setup>) {
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Save changes' }).hasAttribute('disabled')).toBe(false));
    await user.click(screen.getByRole('button', { name: 'Save changes' }));
    await waitFor(() => expect(updateProvider).toHaveBeenCalled());
    return vi.mocked(updateProvider).mock.calls[0][1];
  }

  it.each([
    ['United States', '+1'],
    ['India', '+91'],
    ['Canada', '+1'],
  ])('retains %s selection through navigation, review, and creation', async (country, prefix) => {
    render(<ProviderForm />);
    const user = await beginAdminWizard();
    await user.click(screen.getByRole('checkbox', { name: /Emergency services available/ }));
    if (country !== 'United States') {
      await user.click(screen.getByRole('button', { name: /Country code:/ }));
      await user.type(screen.getByRole('textbox', { name: 'Search countries' }), country);
      await user.keyboard('{Enter}');
    }
    await user.type(screen.getByRole('textbox', { name: 'Emergency contact number' }), '9988776655');
    await user.click(screen.getByRole('button', { name: 'Back' }));
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    expect(screen.getByRole('button', { name: `Country code: ${country} ${prefix}` })).toBeTruthy();
    expect((screen.getByRole('textbox', { name: 'Emergency contact number' }) as HTMLInputElement).value).toBe('9988776655');
    await finishClinicWizard(user);
    expect(screen.getByText(`${prefix} 9988776655`)).toBeTruthy();
    await waitFor(() => expect(screen.getByRole('button', { name: 'Create provider' }).hasAttribute('disabled')).toBe(false));
    await user.click(screen.getByRole('button', { name: 'Create provider' }));
    await waitFor(() => expect(createProvider).toHaveBeenCalledWith(expect.objectContaining({
      emergency_services_available: true, emergency_contact_number: `${prefix} 9988776655`,
    })));
  });

  it('keeps a country-only field invalid, associates its error, and dismisses search', async () => {
    render(<ProviderForm />);
    const user = await beginAdminWizard();
    await user.click(screen.getByRole('checkbox', { name: /Emergency services available/ }));
    await user.click(screen.getByRole('button', { name: /Country code:/ }));
    await user.type(screen.getByRole('textbox', { name: 'Search countries' }), 'India');
    await user.keyboard('{Escape}');
    expect(screen.queryByRole('dialog', { name: 'Select country code' })).toBeNull();
    await user.click(screen.getByRole('button', { name: /Country code:/ }));
    await user.type(screen.getByRole('textbox', { name: 'Search countries' }), 'India');
    await user.keyboard('{Enter}');
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    const error = screen.getByText('Emergency contact number is required.');
    const input = screen.getByRole('textbox', { name: 'Emergency contact number' });
    expect(input.getAttribute('aria-describedby')).toBe(error.id);
    expect(input.getAttribute('aria-invalid')).toBe('true');
    expect(createProvider).not.toHaveBeenCalled();
    await user.type(input, '   ');
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    expect(screen.getByText('Emergency contact number is required.')).toBeTruthy();
  });

  it.each([
    ['+1 403 555 9999', '+1', '403 555 9999'],
    ['+919988776655', '+91', '9988776655'],
    ['+971 50 123 4567', '+971', '50 123 4567'],
    [' 403-555-9999 ', '+1', '403-555-9999'],
    ['+999 123456', '+1', '+999 123456'],
    [null, '+1', ''],
  ])('hydrates %s and preserves it during unrelated edits', async (number, prefix, local) => {
    render(<ProviderForm initialData={existingProvider({ emergency_contact_number: number })} />);
    const user = userEvent.setup();
    await user.type(screen.getByLabelText('Provider / practice name'), ' updated');
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    expect(screen.getByRole('button', { name: new RegExp(`Country code:.*\\${prefix}$`) })).toBeTruthy();
    expect((screen.getByRole('textbox', { name: 'Emergency contact number' }) as HTMLInputElement).value).toBe(local);
    const payload = await saveEdit(user);
    expect(payload).not.toHaveProperty('emergency_contact_number');
    expect(payload).not.toHaveProperty('emergency_services_available');
  });

  it('saves an edited country and local number with one prefix', async () => {
    render(<ProviderForm initialData={existingProvider({ emergency_contact_number: '+919988776655' })} />);
    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    await user.click(screen.getByRole('button', { name: /Country code:/ }));
    await user.type(screen.getByRole('textbox', { name: 'Search countries' }), 'United Kingdom');
    await user.keyboard('{Enter}');
    const input = screen.getByRole('textbox', { name: 'Emergency contact number' });
    await user.clear(input);
    await user.type(input, '2079460000');
    const payload = await saveEdit(user);
    expect(payload).toMatchObject({ emergency_contact_number: '+44 2079460000' });
    expect(screen.getByText('+44 2079460000')).toBeTruthy();
  });

  it('does not duplicate a pasted international prefix', async () => {
    render(<ProviderForm initialData={existingProvider()} />);
    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    fireEvent.change(screen.getByRole('textbox', { name: 'Emergency contact number' }), {
      target: { value: '+44 2079460000' },
    });
    expect(screen.getByRole('button', { name: 'Country code: United Kingdom +44' })).toBeTruthy();
    const payload = await saveEdit(user);
    expect(payload).toMatchObject({ emergency_contact_number: '+44 2079460000' });
  });

  it('blocks clearing an existing required number', async () => {
    render(<ProviderForm initialData={existingProvider()} />);
    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    await user.clear(screen.getByRole('textbox', { name: 'Emergency contact number' }));
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    expect(screen.getByText('Emergency contact number is required.')).toBeTruthy();
    expect(updateProvider).not.toHaveBeenCalled();
  });

  it('clears the submitted number when emergency services are disabled', async () => {
    render(<ProviderForm initialData={existingProvider()} />);
    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    await user.click(screen.getByRole('checkbox', { name: /Emergency services available/ }));
    expect(screen.queryByRole('textbox', { name: 'Emergency contact number' })).toBeNull();
    const payload = await saveEdit(user);
    expect(payload).toMatchObject({ emergency_services_available: false, emergency_contact_number: null });
  });
});

describe('ProviderForm primary address layout', () => {
  it.each(['add', 'edit'] as const)('keeps %s location fields in displayed and keyboard order', async (mode) => {
    const user = userEvent.setup();
    render(<ProviderForm initialData={mode === 'edit' ? existingProvider() : undefined} />);
    if (mode === 'add') await beginAdminWizard();
    else await user.click(screen.getByRole('button', { name: 'Continue' }));
    await user.click(screen.getByRole('button', { name: 'Continue' }));

    // Populate geography so dependent triggers participate in the tab order.
    if (mode === 'add') {
      for (const [label, search, value] of [
        ['Country', 'Search country', 'Canada'],
        ['State / Province', 'Search state / province', 'Alberta'],
        ['City', 'Search city', 'Calgary'],
      ]) {
        await user.click(screen.getByRole('button', { name: label }));
        await user.type(screen.getByRole('combobox', { name: search }), value);
        await user.click(screen.getByRole('option', { name: value }));
        await waitFor(() => expect(document.activeElement).toBe(screen.getByRole('button', { name: label })));
      }
    }
    const fields = [
      screen.getByLabelText('Location name'),
      screen.getByLabelText('Pincode / postal code'),
      ...['Country', 'State / Province', 'City'].map((name) => screen.getByRole('button', { name })),
      screen.getByLabelText('Address line 1'),
      screen.getByLabelText('Address line 2'),
      screen.getByLabelText('Latitude'),
      screen.getByLabelText('Longitude'),
    ];
    fields[0].focus();
    for (let index = 1; index < fields.length; index++) {
      expect(fields[index - 1].compareDocumentPosition(fields[index]) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
      await user.tab();
      expect(document.activeElement).toBe(fields[index]);
    }
    for (const field of fields.slice(5, 7)) {
      expect(field.parentElement?.parentElement?.classList.contains(styles.addressRow)).toBe(true);
    }
    const css = readFileSync('src/components/admin/ProviderForm.module.css', 'utf8');
    expect(css).toMatch(/\.addressRow\s*\{[^}]*grid-column:\s*1\s*\/\s*-1;/);
  });

  it('creates a provider with both address lines after navigating back from review', async () => {
    vi.mocked(createProvider).mockResolvedValue({ id: 'new-provider', photos: [] } as unknown as Provider);
    render(<ProviderForm />);
    const user = await beginAdminWizard();
    await finishClinicWizard(user);
    await user.click(screen.getByRole('button', { name: 'Edit Contact & location' }));
    expect((screen.getByLabelText('Address line 1') as HTMLInputElement).value).toBe('42 Stable Road');
    await user.type(screen.getByLabelText('Address line 2'), 'Suite 200, North wing');
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Create provider' }).hasAttribute('disabled')).toBe(false));
    await user.click(screen.getByRole('button', { name: 'Create provider' }));
    await waitFor(() => expect(createProvider).toHaveBeenCalledWith(expect.objectContaining({
      primary_location: expect.objectContaining({
        address_line_1: '42 Stable Road', address_line_2: 'Suite 200, North wing',
        city: 'Calgary', state_province: 'Alberta', country: 'Canada', postal_code: 'T2P 1J9',
      }),
    })));
  });

  it('prefills and saves changes to both existing address lines', async () => {
    const provider = existingProvider();
    provider.locations[0].address_line_2 = 'Old suite';
    vi.mocked(updateProvider).mockResolvedValue(provider);
    vi.mocked(getProvider).mockResolvedValue(provider);
    render(<ProviderForm initialData={provider} />);
    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    expect((screen.getByLabelText('Address line 1') as HTMLInputElement).value).toBe('12 Main St');
    expect((screen.getByLabelText('Address line 2') as HTMLInputElement).value).toBe('Old suite');
    await user.clear(screen.getByLabelText('Address line 1'));
    await user.type(screen.getByLabelText('Address line 1'), '98 Updated Avenue');
    await user.clear(screen.getByLabelText('Address line 2'));
    await user.type(screen.getByLabelText('Address line 2'), 'New suite');
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Save changes' }).hasAttribute('disabled')).toBe(false));
    await user.click(screen.getByRole('button', { name: 'Save changes' }));
    await waitFor(() => expect(updateProviderLocation).toHaveBeenCalledWith('provider-1', 'location-1', expect.objectContaining({
      name: 'Main branch', address_line_1: '98 Updated Avenue', address_line_2: 'New suite',
      city: 'Calgary', state_province: 'Alberta', country: 'Canada', postal_code: 'T2P 1J9',
    })));
  });
});

describe('ProviderForm visit stability', () => {
  it.each(['CLINIC', 'HOSPITAL'] as const)(
    'keeps %s invitation credentials out of drafts and requires them for final submission',
    async (providerType) => {
      const save = vi.fn().mockResolvedValue(undefined);
      const submit = vi.fn().mockResolvedValue(undefined);
      const user = userEvent.setup();
      const config = invitationConfig({ visit_stability: 'NOT_STABLE_VISIT' }, save, submit);
      config.providerType = providerType;
      render(<ProviderForm invitation={config} />);

      expect(screen.getByText('invited@example.com', { selector: 'strong' })).toBeTruthy();
      await user.click(screen.getByRole('button', { name: 'Save draft' }));
      await waitFor(() => expect(save).toHaveBeenCalled());
      expect(save.mock.calls[0][0]).not.toHaveProperty('password');
      expect(save.mock.calls[0][0]).not.toHaveProperty('password_confirmation');

      await fillInvitationCredentials(user);
      await user.click(screen.getByRole('button', { name: 'Save draft' }));
      await waitFor(() => expect(save).toHaveBeenCalledTimes(2));
      expect((screen.getByLabelText('Password') as HTMLInputElement).value).toBe('');
      expect((screen.getByLabelText('Confirm password') as HTMLInputElement).value).toBe('');
      expect(save.mock.calls[1][0]).not.toHaveProperty('password');
      expect(save.mock.calls[1][0]).not.toHaveProperty('password_confirmation');
      await user.click(screen.getByRole('button', { name: 'Submit for review' }));
      expect(submit).not.toHaveBeenCalled();
      expect(screen.getByText('Use 8–128 characters with upper- and lowercase letters and a number.')).toBeTruthy();
      await fillInvitationCredentials(user);
      await user.clear(screen.getByLabelText('Confirm password'));
      await user.type(screen.getByLabelText('Confirm password'), 'MismatchHorse7');
      await user.click(screen.getByRole('button', { name: 'Submit for review' }));
      expect(submit).not.toHaveBeenCalled();
      expect(screen.getByText('Passwords do not match.')).toBeTruthy();
      await user.clear(screen.getByLabelText('Confirm password'));
      await user.type(screen.getByLabelText('Confirm password'), 'SecureHorse7');
      await user.click(screen.getByRole('button', { name: 'Show password' }));
      expect((screen.getByLabelText('Password') as HTMLInputElement).type).toBe('text');
      await user.click(screen.getByRole('button', { name: 'Submit for review' }));
      await waitFor(() => expect(submit).toHaveBeenCalledWith(expect.objectContaining({
        password: 'SecureHorse7',
        password_confirmation: 'SecureHorse7',
      })));
    }
  );

  it.each(['CLINIC', 'HOSPITAL'] as const)('keeps %s invitation language search, draft and restored selections usable in a dropdown card', async (providerType) => {
    const save = vi.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();
    const config = { ...invitationConfig({ language_ids: ['lang-en'] }, save), providerType };
    const { unmount } = render(<ProviderForm invitation={config} />);
    await screen.findByRole('button', { name: 'Remove English' });
    const trigger = screen.getByRole('button', { name: 'Languages' });
    expect(trigger.closest(`.${styles.dropdownCard}`)).not.toBeNull();
    expect(trigger.closest(`.${styles.invitationLanguageCard}`)).not.toBeNull();
    expect(screen.getByRole('heading', { name: /Contact/ }).closest(`.${styles.dropdownCard}`)).toBeNull();
    const css = readFileSync('src/components/admin/ProviderForm.module.css', 'utf8');
    expect(css).toMatch(/\.form\s+\.dropdownCard\s*\{[^}]*overflow:\s*visible;[^}]*position:\s*relative;[^}]*z-index:\s*5;/);
    expect(css).toMatch(/\.form\s+\.invitationLanguageCard\s*\{[^}]*z-index:\s*6;/);
    await user.click(trigger);
    await user.type(screen.getByRole('searchbox', { name: 'Search languages' }), 'fr');
    expect(screen.queryByRole('option', { name: 'English (en)' })).toBeNull();
    await user.click(screen.getByRole('option', { name: 'French (fr)' }));
    await user.click(screen.getByRole('button', { name: 'Remove English' }));
    await user.click(screen.getByRole('heading', { name: 'Basic information' }));
    expect(screen.queryByRole('listbox', { name: 'Languages' })).toBeNull();
    await user.click(screen.getByRole('button', { name: 'Save draft' }));
    await waitFor(() => expect(save).toHaveBeenCalledWith(expect.objectContaining({ language_ids: ['lang-fr'] })));
    unmount();
    render(<ProviderForm invitation={{ ...config, initial: { ...config.initial, ...save.mock.calls[0][0] } }} />);
    expect(await screen.findByRole('button', { name: 'Remove French' })).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Remove English' })).toBeNull();
  });

  it.each(['CLINIC', 'HOSPITAL'] as const)(
    'prefills and saves zero years of experience in a %s invitation draft',
    async (providerType) => {
      const save = vi.fn().mockResolvedValue(undefined);
      const user = userEvent.setup();
      render(
        <ProviderForm
          invitation={{
            ...invitationConfig({ years_experience: 0 }, save),
            providerType,
          }}
        />
      );

      expect((screen.getByLabelText('Years of experience') as HTMLInputElement).value).toBe('0');
      await user.click(screen.getByRole('button', { name: 'Save draft' }));
      await waitFor(() => expect(save).toHaveBeenCalledWith(
        expect.objectContaining({ years_experience: 0 })
      ));
    }
  );

  it('does not expose general description or clear it in an invitation draft', async () => {
    const save = vi.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();
    render(<ProviderForm invitation={invitationConfig({}, save)} />);
    expect(screen.queryByLabelText('Description')).toBeNull();
    await user.click(screen.getByRole('button', { name: 'Save draft' }));
    await waitFor(() => expect(save).toHaveBeenCalled());
    expect(save.mock.calls[0][0]).not.toHaveProperty('description');
  });

  it.each(['CLINIC', 'HOSPITAL'] as const)(
    'creates a %s with its general description in the review and payload',
    async (providerType) => {
      vi.mocked(createProvider).mockResolvedValue({ id: 'new-provider', photos: [] } as unknown as Provider);
      const user = userEvent.setup();
      render(<ProviderForm />);
      await user.selectOptions(screen.getByRole('combobox', { name: 'Provider type' }), providerType);
      await user.type(screen.getByLabelText('Provider / practice name'), 'North Star');
      const description = screen.getByLabelText(/Description/) as HTMLTextAreaElement;
      expect(description.maxLength).toBe(5000);
      await user.type(description, 'A welcoming local care team.');
      await user.click(screen.getByRole('button', { name: 'Continue' }));
      await finishClinicWizard(user);

      expect(screen.getByText('A welcoming local care team.')).toBeTruthy();
      await waitFor(() => expect(screen.getByRole('button', { name: 'Create provider' }).hasAttribute('disabled')).toBe(false));
      await user.click(screen.getByRole('button', { name: 'Create provider' }));
      await waitFor(() => expect(createProvider).toHaveBeenCalledWith(expect.objectContaining({
        provider_type: providerType,
        description: 'A welcoming local care team.',
      })));
    }
  );

  it.each(['CLINIC', 'HOSPITAL'] as const)(
    'prefills and saves an edited %s description',
    async (providerType) => {
      const provider = existingProvider({ provider_type: providerType, description: 'Existing description' });
      vi.mocked(updateProvider).mockResolvedValue(provider);
      vi.mocked(getProvider).mockResolvedValue(provider);
      const user = userEvent.setup();
      render(<MemoryRouter><ProviderForm initialData={provider} /></MemoryRouter>);
      await reachEditReview(user);

      expect(screen.getByText('Existing description')).toBeTruthy();
      await user.click(screen.getByRole('button', { name: 'Edit Basic details' }));
      const description = screen.getByLabelText(/Description/) as HTMLTextAreaElement;
      expect(description.value).toBe('Existing description');
      await user.clear(description);
      await user.type(description, 'Updated description');
      await user.click(screen.getByRole('button', { name: 'Continue' }));
      await user.click(screen.getByRole('button', { name: 'Continue' }));
      await user.click(screen.getByRole('button', { name: 'Continue' }));
      await waitFor(() => expect(screen.getByRole('button', { name: 'Save changes' }).hasAttribute('disabled')).toBe(false));
      await user.click(screen.getByRole('button', { name: 'Save changes' }));

      await waitFor(() => expect(updateProvider).toHaveBeenCalledWith(
        'provider-1',
        expect.objectContaining({ description: 'Updated description' })
      ));
    }
  );

  it.each(['CLINIC', 'HOSPITAL'] as const)(
    'sends null when the existing %s description is explicitly cleared',
    async (providerType) => {
      const provider = existingProvider({ provider_type: providerType, description: 'Remove this description' });
      vi.mocked(updateProvider).mockResolvedValue(provider);
      vi.mocked(getProvider).mockResolvedValue(provider);
      const user = userEvent.setup();
      render(<ProviderForm initialData={provider} />);
      await reachEditReview(user);
      await user.click(screen.getByRole('button', { name: 'Edit Basic details' }));
      await user.clear(screen.getByLabelText(/Description/));
      await user.click(screen.getByRole('button', { name: 'Continue' }));
      await user.click(screen.getByRole('button', { name: 'Continue' }));
      await user.click(screen.getByRole('button', { name: 'Continue' }));
      await waitFor(() => expect(screen.getByRole('button', { name: 'Save changes' }).hasAttribute('disabled')).toBe(false));
      await user.click(screen.getByRole('button', { name: 'Save changes' }));

      await waitFor(() => expect(updateProvider).toHaveBeenCalledWith(
        'provider-1',
        expect.objectContaining({ description: null })
      ));
    }
  );
  it('prefills the invitation recipient and keeps an explicitly removed address out of the draft', async () => {
    const onSaveDraft = vi.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();
    render(<ProviderForm invitation={invitationConfig({}, onSaveDraft)} />);

    expect((screen.getByRole('textbox', { name: 'Email address 1' }) as HTMLInputElement).value)
      .toBe('invited@example.com');
    await user.click(screen.getByRole('button', { name: 'Remove email 1' }));
    await user.click(screen.getByRole('button', { name: 'Save draft' }));
    await waitFor(() => expect(onSaveDraft).toHaveBeenCalledWith(
      expect.objectContaining({ emails: [] })
    ));
  });

  it('respects a saved empty list and suggests the recipient alongside existing contacts only once', () => {
    const { unmount } = render(
      <ProviderForm invitation={{ ...invitationConfig(), emailsEdited: true }} />
    );
    expect(screen.queryByRole('textbox', { name: 'Email address 1' })).toBeNull();
    unmount();

    render(<ProviderForm invitation={invitationConfig({
      emails: [{ email: 'office@example.com', is_primary: true }],
    })} />);
    expect((screen.getByRole('textbox', { name: 'Email address 1' }) as HTMLInputElement).value)
      .toBe('office@example.com');
    expect((screen.getByRole('textbox', { name: 'Email address 2' }) as HTMLInputElement).value)
      .toBe('invited@example.com');
  });

  it('restores saved invitation service details and addresses', () => {
    render(<ProviderForm invitation={invitationConfig({
      maximum_working_radius_km: 24,
      emergency_services_available: true,
      emergency_contact_number: '+91 9988776655',
      locations: [{ name: 'North barn', address_line_1: '12 Lane', city: 'Delhi', country: 'India', postal_code: '110001', is_primary: true }],
    })} />);
    expect((screen.getByRole('checkbox', { name: 'Offers stable visits' }) as HTMLInputElement).checked).toBe(true);
    expect((screen.getByLabelText('Maximum working radius (km)') as HTMLInputElement).value).toBe('24');
    expect((screen.getByRole('checkbox', { name: 'Emergency services available' }) as HTMLInputElement).checked).toBe(true);
    expect((screen.getByRole('textbox', { name: 'Emergency contact number' }) as HTMLInputElement).value).toBe('9988776655');
    expect((screen.getByLabelText('Location name') as HTMLInputElement).value).toBe('North barn');
    expect((screen.getByLabelText('Postal / ZIP code') as HTMLInputElement).value).toBe('110001');
  });

  it('restores a saved non-stable invitation selection as No', () => {
    render(
      <ProviderForm
        invitation={invitationConfig({ visit_stability: 'NOT_STABLE_VISIT' })}
      />
    );

    expect((screen.getByRole('checkbox', { name: 'Offers stable visits' }) as HTMLInputElement).checked).toBe(false);
    expect(screen.queryByLabelText('Maximum working radius (km)')).toBeNull();
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

    const stable = screen.getByRole('checkbox', { name: 'Offers stable visits' });
    await user.click(stable);
    await user.click(screen.getByRole('button', { name: 'Save draft' }));
    await waitFor(() => expect(onSaveDraft).toHaveBeenCalledWith(
      expect.objectContaining({ visit_stability: 'NOT_STABLE_VISIT', maximum_working_radius_km: null })
    ));

    await user.click(stable);
    await user.type(screen.getByLabelText('Maximum working radius (km)'), '15');
    await fillInvitationCredentials(user);
    await user.click(screen.getByRole('button', { name: 'Submit for review' }));
    await waitFor(() => expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({ visit_stability: 'STABLE_VISIT', maximum_working_radius_km: 15 })
    ));
  });

  it('requires valid conditional services, and clears both dependent values when unchecked', async () => {
    const submit = vi.fn().mockResolvedValue(undefined);
    const draft = vi.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();
    render(<ProviderForm invitation={invitationConfig({}, draft, submit)} />);
    await user.click(screen.getByRole('checkbox', { name: 'Emergency services available' }));
    await user.click(screen.getByRole('button', { name: 'Submit for review' }));
    expect(submit).not.toHaveBeenCalled();
    expect(screen.getByText('Enter a valid emergency number with 6–15 digits.')).toBeTruthy();
    await user.type(screen.getByLabelText('Maximum working radius (km)'), '18');
    await user.type(screen.getByRole('textbox', { name: 'Emergency contact number' }), '9988776655');
    await user.click(screen.getByRole('checkbox', { name: 'Offers stable visits' }));
    await user.click(screen.getByRole('checkbox', { name: 'Emergency services available' }));
    await user.click(screen.getByRole('button', { name: 'Save draft' }));
    await waitFor(() => expect(draft).toHaveBeenCalledWith(expect.objectContaining({
      visit_stability: 'NOT_STABLE_VISIT', maximum_working_radius_km: null,
      emergency_services_available: false, emergency_contact_number: null,
    })));
  });

  it('selects every specialization while a filter is active and retains individually chosen items', async () => {
    const save = vi.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();
    render(<ProviderForm invitation={{ ...invitationConfig({}, save), loadSpecializations: vi.fn().mockResolvedValue(
      Array.from({ length: 8 }, (_, i) => ({ id: `spec-${i}`, name: i === 0 ? 'Dental' : `Care ${i}` }))
    ) }} />);
    await screen.findByRole('button', { name: 'Dental' });
    await user.type(screen.getByPlaceholderText('Filter specializations…'), 'Dental');
    await user.click(screen.getByRole('button', { name: 'Select all specializations' }));
    await user.click(screen.getByRole('button', { name: /Dental/ }));
    await user.click(screen.getByRole('button', { name: 'Save draft' }));
    await waitFor(() => expect(save).toHaveBeenCalledWith(expect.objectContaining({
      specialization_ids: Array.from({ length: 7 }, (_, i) => `spec-${i + 1}`),
    })));
  });

  it('lets an invitee explicitly select a postal match and edit its address lines', async () => {
    vi.mocked(lookupProviderPostalCode).mockResolvedValue({
      status: 'match', candidates: [
        { postal_code: '110001', country: 'India', country_code: 'IN', state_province: 'Delhi', city: 'New Delhi', display_name: 'New Delhi, Delhi' },
        { postal_code: '110001', country: 'India', country_code: 'IN', state_province: 'Delhi', city: 'Delhi Cantonment', display_name: 'Delhi Cantonment' },
      ],
    });
    const save = vi.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();
    render(<ProviderForm invitation={invitationConfig({}, save)} />);
    expect(screen.getAllByLabelText('Location name')).toHaveLength(1);
    expect(screen.queryByRole('button', { name: /Add address|Remove address/i })).toBeNull();
    await user.type(screen.getByLabelText('Postal / ZIP code'), '110001');
    expect(await screen.findByRole('button', { name: 'Delhi Cantonment' })).toBeTruthy();
    expect(screen.getByLabelText('Postal / ZIP code').getAttribute('aria-describedby'))
      .toContain(screen.getByRole('status').id);
    await user.click(screen.getByRole('button', { name: 'New Delhi, Delhi' }));
    expect((screen.getByLabelText('City') as HTMLInputElement).value).toBe('New Delhi');
    await user.clear(screen.getByLabelText('City'));
    await user.type(screen.getByLabelText('City'), 'Corrected Delhi');
    expect((screen.getByLabelText('Address line 1') as HTMLInputElement).value).toBe('');
    await user.type(screen.getByLabelText('Location name'), 'Main');
    await user.type(screen.getByLabelText('Address line 1'), '42 Stable Road');
    await user.click(screen.getByRole('button', { name: 'Save draft' }));
    await waitFor(() => expect(save).toHaveBeenCalledWith(expect.objectContaining({
      locations: [expect.objectContaining({ name: 'Main', address_line_1: '42 Stable Road', city: 'Corrected Delhi', postal_code: '110001', is_primary: true })],
    })));
  });

  it('lets hospital invitees save an empty address and choose manual entry after postal matches', async () => {
    vi.mocked(lookupProviderPostalCode).mockResolvedValue({
      status: 'match', candidates: [
        { postal_code: '110001', country: 'India', country_code: 'IN', state_province: 'Delhi', city: 'New Delhi', display_name: 'New Delhi, India' },
      ],
    });
    const save = vi.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();
    render(<ProviderForm invitation={{ ...invitationConfig({}, save), providerType: 'HOSPITAL' }} />);
    await user.click(screen.getByRole('button', { name: 'Save draft' }));
    await waitFor(() => expect(save).toHaveBeenCalledWith(expect.objectContaining({ locations: [] })));
    await user.type(screen.getByLabelText('Postal / ZIP code'), '110001');
    await screen.findByRole('button', { name: 'New Delhi, India' });
    await user.click(screen.getByRole('button', { name: 'Enter location manually' }));
    expect(screen.queryByRole('button', { name: 'New Delhi, India' })).toBeNull();
    await user.type(screen.getByLabelText('Location name'), 'West hospital');
    await user.type(screen.getByLabelText('Country'), 'India');
    await user.type(screen.getByLabelText('City'), 'Agra');
    await user.type(screen.getByLabelText('Address line 1'), '9 Hill Rd');
    await user.type(screen.getByLabelText('Address line 2'), 'Suite 2');
    await user.click(screen.getByRole('button', { name: 'Save draft' }));
    await waitFor(() => expect(save).toHaveBeenLastCalledWith(expect.objectContaining({
      locations: [expect.objectContaining({ name: 'West hospital', city: 'Agra', address_line_2: 'Suite 2', is_primary: true })],
    })));
  });

  it('saves a changed emergency country code and accepts manual addresses when lookup is unavailable', async () => {
    vi.stubGlobal('matchMedia', () => ({ matches: false }));
    Element.prototype.scrollIntoView = vi.fn();
    vi.mocked(lookupProviderPostalCode).mockResolvedValue({ status: 'unavailable', candidates: [] });
    const save = vi.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();
    render(<ProviderForm invitation={invitationConfig({ visit_stability: 'NOT_STABLE_VISIT' }, save)} />);
    await user.click(screen.getByRole('checkbox', { name: 'Emergency services available' }));
    await user.click(screen.getByRole('button', { name: /Country code:/ }));
    await user.type(screen.getByRole('textbox', { name: 'Search countries' }), 'India');
    await user.click(screen.getByRole('option', { name: /India/ }));
    await user.type(screen.getByRole('textbox', { name: 'Emergency contact number' }), '9988776655');
    await user.type(screen.getByLabelText('Postal / ZIP code'), '110001');
    expect(await screen.findByText('Postal lookup is unavailable. You can enter the address manually.')).toBeTruthy();
    await user.type(screen.getByLabelText('Location name'), 'South branch');
    await user.type(screen.getByLabelText('Address line 1'), '12 Road');
    await user.type(screen.getByLabelText('City'), 'Delhi');
    await user.type(screen.getByLabelText('Country'), 'India');
    await user.click(screen.getByRole('button', { name: 'Save draft' }));
    await waitFor(() => expect(save).toHaveBeenCalledWith(expect.objectContaining({
      emergency_contact_number: '+91 9988776655',
      locations: [expect.objectContaining({ name: 'South branch', city: 'Delhi', country: 'India' })],
    })));
  });

  it('requires a legacy address choice before saving or submitting a clinic invitation', async () => {
    const save = vi.fn().mockResolvedValue(undefined);
    const submit = vi.fn().mockResolvedValue(undefined);
    const locations = [
      { name: 'First', address_line_1: '1 First St', city: 'Delhi', is_primary: true },
      { name: 'Second', address_line_1: '2 Second St', city: 'Mumbai', is_primary: false },
    ];
    const user = userEvent.setup();
    render(<ProviderForm invitation={invitationConfig({ locations, visit_stability: 'NOT_STABLE_VISIT' }, save, submit)} />);
    expect(screen.queryByLabelText('Location name')).toBeNull();
    await user.click(screen.getByRole('button', { name: 'Save draft' }));
    await user.click(screen.getByRole('button', { name: 'Submit for review' }));
    expect(save).not.toHaveBeenCalled();
    expect(submit).not.toHaveBeenCalled();
    await user.click(screen.getByRole('button', { name: /Keep Second/ }));
    expect((screen.getByLabelText('Location name') as HTMLInputElement).value).toBe('Second');
    await user.click(screen.getByRole('button', { name: 'Save draft' }));
    await waitFor(() => expect(save).toHaveBeenCalledWith(expect.objectContaining({
      locations: [expect.objectContaining({ name: 'Second', is_primary: true })],
    })));
    await fillInvitationCredentials(user);
    await user.click(screen.getByRole('button', { name: 'Submit for review' }));
    await waitFor(() => expect(submit).toHaveBeenCalledWith(expect.objectContaining({
      locations: [expect.objectContaining({ name: 'Second', is_primary: true })],
    })));
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
    expect(screen.getByRole('button', { name: 'Languages' })).toBeTruthy();
    expect(screen.queryByLabelText('Profile photo')).toBeNull();
    expect(screen.queryByText('Clinic / hospital visits')).toBeNull();
  });

  it('selects invitation languages from the public catalog, saves, restores, and submits them', async () => {
    const save = vi.fn().mockResolvedValue(undefined);
    const submit = vi.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();
    const initial = invitationConfig({
      visit_stability: 'NOT_STABLE_VISIT',
      language_ids: ['lang-fr'],
    }, save, submit);
    const { unmount } = render(<ProviderForm invitation={initial} />);

    await waitFor(() => expect(listProviderSignupLanguages).toHaveBeenCalled());
    expect(screen.getByRole('button', { name: 'Remove French' })).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'Languages' }));
    expect(screen.getByRole('option', { name: /French/ }).getAttribute('aria-selected')).toBe('true');
    await user.click(screen.getByRole('option', { name: /French/ }));
    await user.click(screen.getByRole('button', { name: 'Select all' }));
    expect(screen.getByRole('option', { name: /English/ }).getAttribute('aria-selected')).toBe('true');
    expect(screen.getByRole('option', { name: /French/ }).getAttribute('aria-selected')).toBe('true');
    await user.click(screen.getByRole('button', { name: 'Save draft' }));
    await waitFor(() => expect(save).toHaveBeenCalledWith(expect.objectContaining({
      language_ids: ['lang-en', 'lang-fr'],
    })));

    unmount();
    const savedIds = save.mock.calls[0][0].language_ids;
    render(<ProviderForm invitation={invitationConfig({
      visit_stability: 'NOT_STABLE_VISIT',
      language_ids: savedIds,
    }, save, submit)} />);
    await waitFor(() => expect(screen.getByRole('button', { name: 'Remove English' })).toBeTruthy());
    expect(screen.getByRole('button', { name: 'Remove French' })).toBeTruthy();
    await fillInvitationCredentials(user);
    await user.click(screen.getByRole('button', { name: 'Submit for review' }));
    await waitFor(() => expect(submit).toHaveBeenCalledWith(expect.objectContaining({
      language_ids: ['lang-en', 'lang-fr'],
    })));
  });

  it('shows a public language-catalog error without dropping previously saved ids', async () => {
    vi.mocked(listProviderSignupLanguages).mockRejectedValueOnce(new Error('Catalog unavailable'));
    const save = vi.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();
    render(<ProviderForm invitation={invitationConfig({
      language_ids: ['retired-language'],
    }, save)} />);

    expect(await screen.findByText('Failed to load languages.')).toBeTruthy();
    expect(screen.getByText('Failed to load languages.').getAttribute('role')).toBe('alert');
    await user.click(screen.getByRole('button', { name: 'Save draft' }));
    await waitFor(() => expect(save).toHaveBeenCalledWith(expect.objectContaining({
      language_ids: ['retired-language'],
    })));
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
    expect(number.type).toBe('tel');
    expect(screen.getByRole('button', { name: 'Country code: United States +1' })).toBeTruthy();
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

    await waitFor(() => expect(onSuccess).toHaveBeenCalled());
    expect(onSuccess.mock.calls[0][0]).toBe(saved);
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

  it('sends portal access to the selected address when opted in at review', async () => {
    const saved = { id: 'provider-portal', photos: [] } as unknown as Provider;
    const onSuccess = vi.fn();
    vi.mocked(createProvider).mockResolvedValue(saved);
    vi.mocked(getProviderPortalAccess).mockResolvedValue({
      status: 'eligible', recipient_email: null, email_id: null, invitation_id: null,
      sent_at: null, message: null,
      can_revoke: false,
      selectable_emails: [{ email_id: 'email-clinic', email: 'clinic@example.com' }],
    });
    vi.mocked(sendProviderPortalAccess).mockResolvedValue({
      status: 'pending', recipient_email: 'clinic@example.com', email_id: 'email-clinic',
      invitation_id: 'invitation-1', sent_at: '2025-01-01T00:00:00Z', message: 'Email sent',
      can_revoke: true,
      selectable_emails: [{ email_id: 'email-clinic', email: 'clinic@example.com' }],
    });

    render(<ProviderForm onSuccess={onSuccess} />);
    const user = await beginAdminWizard();
    await finishClinicWizard(user);

    const optIn = screen.getByRole('checkbox', { name: 'Send portal access email after creating this provider' });
    expect((optIn as HTMLInputElement).checked).toBe(false);
    await user.click(optIn);
    await user.selectOptions(screen.getByRole('combobox', { name: 'Portal access recipient' }), 'clinic@example.com');
    await waitFor(() => expect(screen.getByRole('button', { name: 'Create provider' }).hasAttribute('disabled')).toBe(false));
    await user.click(screen.getByRole('button', { name: 'Create provider' }));

    await waitFor(() => expect(sendProviderPortalAccess).toHaveBeenCalledWith('provider-portal', 'email-clinic'));
    expect(getProviderPortalAccess).toHaveBeenCalledWith('provider-portal');
    expect(onSuccess.mock.calls[0][0]).toBe(saved);
    expect(onSuccess.mock.calls[0][2]).toBe('clinic@example.com');
    expect(createProvider).toHaveBeenCalledTimes(1);
    expect(vi.mocked(createProvider).mock.calls[0][0]).not.toHaveProperty('send_portal_access');
  });

  it('keeps the saved provider and reports the chosen recipient when access email delivery fails', async () => {
    const saved = { id: 'provider-mail-error', photos: [] } as unknown as Provider;
    const onSuccess = vi.fn();
    vi.mocked(createProvider).mockResolvedValue(saved);
    vi.mocked(getProviderPortalAccess).mockResolvedValue({
      status: 'eligible', recipient_email: null, email_id: null, invitation_id: null,
      sent_at: null, message: null,
      can_revoke: false,
      selectable_emails: [{ email_id: 'email-clinic', email: 'clinic@example.com' }],
    });
    vi.mocked(sendProviderPortalAccess).mockRejectedValue(new Error('Mail service unavailable'));

    render(<ProviderForm onSuccess={onSuccess} />);
    const user = await beginAdminWizard();
    await finishClinicWizard(user);
    await user.click(screen.getByRole('checkbox', { name: 'Send portal access email after creating this provider' }));
    await user.selectOptions(screen.getByRole('combobox', { name: 'Portal access recipient' }), 'clinic@example.com');
    await waitFor(() => expect(screen.getByRole('button', { name: 'Create provider' }).hasAttribute('disabled')).toBe(false));
    await user.click(screen.getByRole('button', { name: 'Create provider' }));

    await waitFor(() => expect(onSuccess).toHaveBeenCalled());
    expect(onSuccess.mock.calls[0][0]).toBe(saved);
    expect(onSuccess.mock.calls[0][1]).toEqual(expect.objectContaining({
      recipient_email: 'clinic@example.com',
      email_id: 'email-clinic',
      message: expect.any(String),
    }));
    expect(sendProviderPortalAccess).toHaveBeenCalledWith('provider-mail-error', 'email-clinic');
    expect(createProvider).toHaveBeenCalledTimes(1);
    expect(screen.queryByText(/Failed to save provider/)).toBeNull();
  });

  it('does not request or send portal access when the review opt-in is left off', async () => {
    const saved = { id: 'provider-opt-out', photos: [] } as unknown as Provider;
    const onSuccess = vi.fn();
    vi.mocked(createProvider).mockResolvedValue(saved);

    render(<ProviderForm onSuccess={onSuccess} />);
    const user = await beginAdminWizard();
    await finishClinicWizard(user);
    expect((screen.getByRole('checkbox', { name: 'Send portal access email after creating this provider' }) as HTMLInputElement).checked).toBe(false);
    await waitFor(() => expect(screen.getByRole('button', { name: 'Create provider' }).hasAttribute('disabled')).toBe(false));
    await user.click(screen.getByRole('button', { name: 'Create provider' }));

    await waitFor(() => expect(onSuccess).toHaveBeenCalled());
    expect(onSuccess.mock.calls[0][0]).toBe(saved);
    expect(getProviderPortalAccess).not.toHaveBeenCalled();
    expect(sendProviderPortalAccess).not.toHaveBeenCalled();
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
  it('keeps legacy Doctor descriptions hidden and omitted from admin update payloads', async () => {
    const provider = existingProvider({
      provider_type: 'DOCTOR',
      description: 'Legacy description',
    });
    vi.mocked(updateProvider).mockResolvedValue(provider);
    vi.mocked(getProvider).mockResolvedValue(provider);
    const user = userEvent.setup();
    render(<ProviderForm initialData={provider} />);
    expect(screen.queryByLabelText('Description')).toBeNull();
    await reachEditReview(user, true);
    await waitFor(() => expect(screen.getByRole('button', { name: 'Save changes' }).hasAttribute('disabled')).toBe(false));
    await user.click(screen.getByRole('button', { name: 'Save changes' }));

    await waitFor(() => expect(updateProvider).toHaveBeenCalled());
    expect(vi.mocked(updateProvider).mock.calls[0][1]).not.toHaveProperty('description');
  });

  it('omits a hospital description when the provider type is switched to Doctor', async () => {
    const provider = existingProvider({
      provider_type: 'HOSPITAL',
      description: 'Hospital description',
    });
    vi.mocked(updateProvider).mockResolvedValue(provider);
    vi.mocked(getProvider).mockResolvedValue(provider);
    const user = userEvent.setup();
    render(<ProviderForm initialData={provider} />);
    expect((screen.getByLabelText(/Description/) as HTMLTextAreaElement).value).toBe('Hospital description');
    await user.selectOptions(screen.getByRole('combobox', { name: 'Provider type' }), 'DOCTOR');
    expect(screen.queryByLabelText('Description')).toBeNull();
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    await user.type(screen.getByLabelText('First name'), 'Amina');
    await user.type(screen.getByLabelText('Last name'), 'Khan');
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Save changes' }).hasAttribute('disabled')).toBe(false));
    await user.click(screen.getByRole('button', { name: 'Save changes' }));

    await waitFor(() => expect(updateProvider).toHaveBeenCalledWith(
      'provider-1',
      expect.objectContaining({ provider_type: 'DOCTOR' })
    ));
    expect(vi.mocked(updateProvider).mock.calls[0][1]).not.toHaveProperty('description');
  });

  it.each(['CLINIC', 'HOSPITAL'] as const)(
    'prefills and updates zero years of experience when editing a %s',
    async (providerType) => {
      const provider = existingProvider({ provider_type: providerType, years_experience: 0 });
      vi.mocked(updateProvider).mockResolvedValue(provider);
      vi.mocked(getProvider).mockResolvedValue(provider);
      const user = userEvent.setup();
      render(<ProviderForm initialData={provider} />);

      expect((screen.getByLabelText('Years of experience') as HTMLInputElement).value).toBe('0');
      await reachEditReview(user);
      await waitFor(() => expect(screen.getByRole('button', { name: 'Save changes' }).hasAttribute('disabled')).toBe(false));
      await user.click(screen.getByRole('button', { name: 'Save changes' }));

      await waitFor(() => expect(updateProvider).toHaveBeenCalledWith(
        'provider-1',
        expect.objectContaining({ years_experience: 0 })
      ));
    }
  );

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
    expect(screen.getByRole('button', { name: 'Country code: United States +1' })).toBeTruthy();
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

  it('restores a gallery-selected profile photo after remount and saves without re-uploading it', async () => {
    const provider = existingProvider({
      thumbnail_url: '/uploads/gallery-selected.webp',
      photos: [
        { id: 'photo-1', storage_reference: '/uploads/old.webp', is_thumbnail: false },
        { id: 'photo-2', storage_reference: '/uploads/gallery-selected.webp', is_thumbnail: true },
      ] as Provider['photos'],
    });
    vi.mocked(updateProvider).mockResolvedValue(provider);
    const { unmount } = render(<MemoryRouter><ProviderForm initialData={provider} /></MemoryRouter>);
    expect((screen.getByRole('img', { name: 'Profile preview' }) as HTMLImageElement).getAttribute('src'))
      .toBe('/uploads/gallery-selected.webp');
    unmount();
    render(<MemoryRouter><ProviderForm initialData={provider} /></MemoryRouter>);
    const user = userEvent.setup();
    await reachEditReview(user);
    expect((screen.getByRole('img', { name: 'Current provider profile photo' }) as HTMLImageElement).getAttribute('src'))
      .toBe('/uploads/gallery-selected.webp');
    await waitFor(() => expect(screen.getByRole('button', { name: 'Save changes' }).hasAttribute('disabled')).toBe(false));
    await user.click(screen.getByRole('button', { name: 'Save changes' }));
    await waitFor(() => expect(updateProvider).toHaveBeenCalled());
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
    expect((screen.getByLabelText('Emergency contact number') as HTMLInputElement).value).toBe('403 555 9999');
    expect(screen.getByRole('button', { name: 'Country code: United States +1' })).toBeTruthy();
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

describe('Admin doctor availability and initial visit UI', () => {
  async function beginDoctor(user: ReturnType<typeof userEvent.setup>) {
    await user.selectOptions(screen.getByRole('combobox', { name: 'Provider type' }), 'DOCTOR');
    await user.type(screen.getByLabelText('Provider / practice name'), 'Prairie Equine Care');
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    await user.type(screen.getByLabelText('First name'), 'Maya');
    await user.type(screen.getByLabelText('Last name'), 'Singh');
    await user.click(screen.getByRole('button', { name: 'Continue' }));
  }

  it.each(['CLINIC', 'HOSPITAL'])('shows exactly two defaulted doctor options, never on a %s', async (type) => {
    const user = userEvent.setup();
    render(<ProviderForm />);
    await user.selectOptions(screen.getByRole('combobox', { name: 'Provider type' }), type);
    await user.type(screen.getByLabelText('Provider / practice name'), 'Meadow Clinic');
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    expect(screen.queryByLabelText('Availability')).toBeNull();
    cleanup();

    render(<ProviderForm />);
    await beginDoctor(user);
    const availability = screen.getByLabelText('Availability') as HTMLSelectElement;
    expect(Array.from(availability.options).map((option) => [option.value, option.text])).toEqual([
      ['ONGOING', 'Ongoing'], ['VISITING', 'Visiting'],
    ]);
    expect(availability.value).toBe('ONGOING');
    expect(screen.queryByLabelText('Start date')).toBeNull();
    await user.selectOptions(screen.getByLabelText('Availability'), 'VISITING');
    expect(screen.getByLabelText('Start date')).toBeTruthy();
    expect(screen.getByLabelText('End date')).toBeTruthy();
    expect(screen.getByLabelText('Address line 1')).toBeTruthy();
  });

  it('creates an ongoing doctor without touching availability and reviews the persisted default', async () => {
    vi.mocked(createProvider).mockResolvedValue({ id: 'doctor-ongoing', photos: [] } as unknown as Provider);
    const user = userEvent.setup();
    render(<ProviderForm />);
    await beginDoctor(user);
    await finishClinicWizard(user);
    expect(screen.getByText('Ongoing')).toBeTruthy();
    await waitFor(() => expect(screen.getByRole('button', { name: 'Create provider' }).hasAttribute('disabled')).toBe(false));
    await user.click(screen.getByRole('button', { name: 'Create provider' }));
    await waitFor(() => expect(createProvider).toHaveBeenCalledWith(expect.objectContaining({
      provider_type: 'DOCTOR', doctor_availability: 'ONGOING',
    })));
    expect(vi.mocked(createProvider).mock.calls[0][0]).not.toHaveProperty('initial_visit');
  });

  it('rejects incomplete and reversed initial visits while allowing a blank optional visit', async () => {
    const user = userEvent.setup();
    render(<ProviderForm />);
    await beginDoctor(user);
    await user.selectOptions(screen.getByLabelText('Availability'), 'VISITING');
    await user.type(screen.getByLabelText('Start date'), '2026-06-03');
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    expect(screen.getByText('Complete the initial visit location and both dates, or leave it unscheduled.')).toBeTruthy();
    await user.type(screen.getByLabelText('Address line 1'), '1 Prairie Way');
    await user.type(screen.getByLabelText('City'), 'Calgary');
    await user.type(screen.getByLabelText('End date'), '2026-06-01');
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    expect(screen.getByText('End date must be on or after the start date.')).toBeTruthy();
    expect(createProvider).not.toHaveBeenCalled();
  });

  it('saves a visiting Doctor without a visit when the optional fields stay blank', async () => {
    const user = userEvent.setup();
    vi.mocked(createProvider).mockResolvedValue({ id: 'doctor-unscheduled', photos: [] } as unknown as Provider);
    render(<ProviderForm />);
    await beginDoctor(user);
    await user.selectOptions(screen.getByLabelText('Availability'), 'VISITING');
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    await user.click(screen.getByRole('button', { name: /Add email/i }));
    await user.type(screen.getByRole('textbox', { name: 'Email address 1' }), 'maya@example.com');
    await user.type(screen.getByLabelText('Address line 1'), '1 Prairie Way');
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
    await waitFor(() => expect(screen.getByRole('button', { name: 'Create provider' }).hasAttribute('disabled')).toBe(false));
    await user.click(screen.getByRole('button', { name: 'Create provider' }));
    await waitFor(() => expect(createProvider).toHaveBeenCalledWith(expect.objectContaining({
      provider_type: 'DOCTOR',
      doctor_availability: 'VISITING',
    })));
    expect(screen.queryByLabelText('Description')).toBeNull();
    expect(vi.mocked(createProvider).mock.calls[0][0]).not.toHaveProperty('description');
    expect(vi.mocked(createProvider).mock.calls[0][0]).not.toHaveProperty('initial_visit');
  });

  it('includes a complete initial visit in review and save payload', async () => {
    const user = userEvent.setup();
    vi.mocked(createProvider).mockResolvedValue({ id: 'doctor-visit', photos: [] } as unknown as Provider);
    render(<ProviderForm />);
    await beginDoctor(user);
    await user.selectOptions(screen.getByLabelText('Availability'), 'VISITING');
    await user.type(screen.getByLabelText('Address line 1'), '1 Prairie Way');
    await user.type(screen.getByLabelText('City'), 'Calgary');
    await user.type(screen.getByLabelText('Start date'), '2026-06-01');
    await user.type(screen.getByLabelText('End date'), '2026-06-03');
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    await user.click(screen.getByRole('button', { name: /Add email/i }));
    await user.type(screen.getByRole('textbox', { name: 'Email address 1' }), 'maya@example.com');
    await user.type(screen.getByLabelText('Address line 1'), '1 Prairie Way');
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
    expect(screen.getByText(/2026-06-01 to 2026-06-03/)).toBeTruthy();
    await waitFor(() => expect(screen.getByRole('button', { name: 'Create provider' }).hasAttribute('disabled')).toBe(false));
    await user.click(screen.getByRole('button', { name: 'Create provider' }));
    await waitFor(() => expect(createProvider).toHaveBeenCalledWith(expect.objectContaining({
      initial_visit: expect.objectContaining({
        start_date: '2026-06-01',
        end_date: '2026-06-03',
        location: expect.objectContaining({ address_line_1: '1 Prairie Way', city: 'Calgary' }),
      }),
    })));
  });

  it.each([null, undefined, 'ONGOING', 'VISITING'] as const)('reviews and saves %s doctor availability without interaction', async (availability) => {
    const provider = existingProvider({
      provider_type: 'DOCTOR',
      doctor_profile: { first_name: 'Maya', last_name: 'Singh', professional_title: null, biography: null, years_experience: null, experience_description: null },
      doctor_availability: availability,
      doctor_visits: availability === 'VISITING' ? [{
        id: 'visit-1', location: { address_line_1: '1 Prairie Way', city: 'Calgary' },
        start_date: '2026-06-01', end_date: '2026-06-03',
      }] : [],
    });
    vi.mocked(updateProvider).mockResolvedValue(provider);
    vi.mocked(getProvider).mockResolvedValue(provider);
    const user = userEvent.setup();
    render(<ProviderForm initialData={provider} />);
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    expect((screen.getByLabelText('Availability') as HTMLSelectElement).value).toBe(availability ?? 'ONGOING');
    expect(screen.queryByLabelText('Start date')).toBeNull();
    expect(updateProvider).not.toHaveBeenCalled();
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    expect(screen.getByText(availability === 'VISITING' ? 'Visiting' : 'Ongoing')).toBeTruthy();
    await waitFor(() => expect(screen.getByRole('button', { name: 'Save changes' }).hasAttribute('disabled')).toBe(false));
    await user.click(screen.getByRole('button', { name: 'Save changes' }));
    await waitFor(() => expect(updateProvider).toHaveBeenCalled());
    expect(vi.mocked(updateProvider).mock.calls[0][1]).toMatchObject({
      doctor_availability: availability ?? 'ONGOING',
    });
    expect(vi.mocked(updateProvider).mock.calls[0][1]).not.toHaveProperty('doctor_visits');
    expect(vi.mocked(updateProvider).mock.calls[0][1]).not.toHaveProperty('initial_visit');
  });

  it('does not write missing availability when the administrator opens and cancels the editor', async () => {
    const provider = existingProvider({ provider_type: 'DOCTOR', doctor_availability: null });
    const onCancel = vi.fn();
    const user = userEvent.setup();
    render(<ProviderForm initialData={provider} onCancel={onCancel} />);
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    expect((screen.getByLabelText('Availability') as HTMLSelectElement).value).toBe('ONGOING');
    await user.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(onCancel).toHaveBeenCalledOnce();
    expect(updateProvider).not.toHaveBeenCalled();
    expect(provider.doctor_availability).toBeNull();
  });
});