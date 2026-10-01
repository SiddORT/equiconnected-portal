import { describe, expect, it, vi, afterEach, beforeEach } from 'vitest';
import { act, cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { createElement } from 'react';
import type { ProviderRegistrationRequest } from '@/types';
import { ProviderSignupPage, validateProviderSignup } from './ProviderSignupPage';
import * as authApi from '@/api/auth';

vi.mock('@/api/auth', () => ({
  listProviderSignupSpecializations: vi.fn().mockResolvedValue([
    { id: 'spec-a', name: 'Dental care' },
    { id: 'spec-b', name: 'Dental surgery' },
    { id: 'spec-c', name: 'Emergency care' },
  ]),
  listProviderSignupLanguages: vi.fn().mockResolvedValue([
    { id: 'lang-en', name: 'English', code: 'en' },
    { id: 'lang-fr', name: 'French', code: 'fr' },
    { id: 'lang-de', name: 'German', code: 'de' },
  ]),
  registerProvider: vi.fn().mockResolvedValue({}),
  resendVerification: vi.fn(),
  lookupProviderPostalCode: vi.fn().mockResolvedValue({ status: 'no_match', candidates: [] }),
}));
vi.mock('@/components/ui/LocationPicker', () => ({
  LocationPicker: ({ onChange, value }: {
    onChange: (value: object) => void;
    value: { country: string; state_province: string; city: string };
  }) => createElement('div', null,
    createElement('button', { type: 'button', onClick: () => onChange({ country: 'Canada', state_province: 'Alberta', city: 'Calgary' }) }, 'Choose test location'),
    createElement('output', { 'data-testid': 'signup-location-values' },
      [value.country, value.state_province, value.city].join('|')),
  ),
}));
beforeEach(() => {
  vi.stubGlobal('matchMedia', () => ({ matches: false }));
  Element.prototype.scrollIntoView = vi.fn();
});
afterEach(() => { cleanup(); vi.clearAllMocks(); vi.unstubAllGlobals(); });

const validApplication: ProviderRegistrationRequest = {
  first_name: 'Amina',
  last_name: 'Veterinarian',
  email: 'amina@example.com',
  mobile_number: '50 123 4567',
  country: 'United States',
  state_province: 'California',
  city: 'Los Angeles',
  postal_code: '90001',
  password: 'HorseCare2026',
  password_confirmation: 'HorseCare2026',
  role: 'PROVIDER',
  provider_type: 'CLINIC',
  provider_name: 'Amina Equine Clinic',
  visit_stability: 'STABLE_VISIT',
  professional_title: 'Equine veterinarian',
  specialization_ids: ['dc06ab91-4687-44cf-acef-47fa29ef80ad'],
  language_ids: [],
  years_experience: 8,
  working_address: '12 Stable Lane',
  stable_visit: true,
  maximum_working_radius_km: 40,
  emergency_services_available: false,
  emergency_contact_number: null,
  accept_terms: true,
  accept_privacy: true,
};

describe('provider registration validation', () => {
  it('requires the listing essentials and a complete location', () => {
    const errors = validateProviderSignup({
      ...validApplication,
      provider_name: '',
      working_address: '',
    });
    expect(errors.provider_name).toBe('This field is required');
    expect(errors.working_address).toBe('This field is required');
    expect(errors.state_province).toBeUndefined();
  });

  it('accepts a valid provider application with one selected provider type', () => {
    expect(validateProviderSignup(validApplication)).toEqual({});
  });

  it('requires radius only for stable visits and an emergency number only for emergency services', () => {
    expect(validateProviderSignup({
      ...validApplication, maximum_working_radius_km: null,
      emergency_services_available: true, emergency_contact_number: null,
    })).toMatchObject({
      maximum_working_radius_km: 'Enter a working radius greater than 0 km',
      emergency_contact_number: 'Emergency contact number is required',
    });
    expect(validateProviderSignup({
      ...validApplication, stable_visit: false, visit_stability: 'NOT_STABLE_VISIT',
      maximum_working_radius_km: null,
    })).toEqual({});
  });

  it('validates the local emergency digits and the API-length international value', () => {
    const enabled = { ...validApplication, emergency_services_available: true };
    expect(validateProviderSignup({ ...enabled, emergency_contact_number: '12345' }).emergency_contact_number)
      .toMatch(/6–15 digits/);
    expect(validateProviderSignup({ ...enabled, emergency_contact_number: '123456x' }).emergency_contact_number)
      .toMatch(/valid emergency/);
    expect(validateProviderSignup({ ...enabled, emergency_contact_number: '123456789012345' }, '+971'))
      .toEqual({});
    expect(validateProviderSignup({
      ...enabled, emergency_contact_number: '1 2 3 4 5 6 7 8 9 0 1 2 3 4 5',
    }, '+971').emergency_contact_number).toMatch(/valid emergency/);
  });

  it('requires an active specialization selection and professional experience', () => {
    expect(validateProviderSignup({
      ...validApplication, specialization_ids: [], years_experience: null,
    })).toMatchObject({
      specialization_ids: 'Select at least one specialization',
      years_experience: 'Enter years of experience between 0 and 100',
    });
  });
});

async function fillRequiredProviderFields(user: ReturnType<typeof userEvent.setup>) {
  render(createElement(MemoryRouter, null, createElement(ProviderSignupPage)));
  await screen.findByRole('button', { name: /Specializations/ });
  await user.click(screen.getByRole('button', { name: /Specializations/ }));
  await user.click(screen.getByRole('option', { name: 'Emergency care' }));
  await user.click(screen.getByRole('button', { name: /Specializations/ }));
  await user.type(screen.getByLabelText('Provider or practice name'), 'Equine Clinic');
  await user.type(screen.getByLabelText('First name'), 'Amina');
  await user.type(screen.getByLabelText('Last name'), 'Vet');
  await user.type(screen.getByLabelText('Email address'), 'amina@example.com');
  await user.type(screen.getByLabelText('Mobile number'), '5551234567');
  await user.type(screen.getByLabelText('Professional title'), 'Veterinarian');
  await user.type(screen.getByLabelText('Years of experience'), '8');
  await user.type(screen.getByLabelText('Pincode / postal code'), 'T2P 1J9');
  await user.click(screen.getByRole('button', { name: 'Choose test location' }));
  await user.type(screen.getByLabelText('Address'), '42 Stable Road');
  await user.type(screen.getByLabelText('Password', { exact: true }), 'HorseCare2026');
  await user.type(screen.getByLabelText('Confirm password'), 'HorseCare2026');
  await user.click(document.getElementById('provider-accept-terms')!);
  await user.click(document.getElementById('provider-accept-privacy')!);
}

describe('provider signup emergency phone picker', () => {
  it('shows a searchable, keyboard-selectable country without changing the mobile code and submits an international emergency number', async () => {
    const user = userEvent.setup();
    await fillRequiredProviderFields(user);
    expect(screen.queryByLabelText('Emergency contact number')).toBeNull();
    await user.click(screen.getByLabelText('Emergency services available'));
    const emergency = screen.getByLabelText('Emergency contact number');
    const [mobilePicker, emergencyPicker] = screen.getAllByRole('button', { name: /Country code: United States \+1/ });
    await user.click(emergencyPicker);
    const search = screen.getByRole('textbox', { name: 'Search countries' });
    await user.type(search, 'United Kingdom');
    expect(screen.getByRole('option', { name: /United Kingdom.*\+44/ })).toBeTruthy();
    await user.keyboard('{Enter}');
    expect(emergencyPicker.getAttribute('aria-label')).toBe('Country code: United Kingdom +44');
    expect(mobilePicker.getAttribute('aria-label')).toBe('Country code: United States +1');
    await user.type(emergency, '20 1234 5678');
    await user.click(screen.getByRole('button', { name: 'Submit provider application' }));
    await waitFor(() => expect(authApi.registerProvider).toHaveBeenCalledWith(expect.objectContaining({
      mobile_number: '+1 5551234567',
      emergency_services_available: true,
      emergency_contact_number: '+44 20 1234 5678',
    })));
  });

  it('blocks empty and invalid emergency numbers, then clears the number when emergency services are switched off', async () => {
    const user = userEvent.setup();
    await fillRequiredProviderFields(user);
    const toggle = screen.getByLabelText('Emergency services available');
    const submit = screen.getByRole('button', { name: 'Submit provider application' });
    await user.click(toggle);
    await user.click(submit);
    expect(screen.getByRole('alert', { name: '' }).textContent).toContain('Emergency contact number is required');
    expect(authApi.registerProvider).not.toHaveBeenCalled();
    const emergency = screen.getByLabelText('Emergency contact number');
    await user.type(emergency, '123x');
    await user.click(submit);
    expect(screen.getByText(/Enter a valid emergency number with 6–15 digits/)).toBeTruthy();
    expect(authApi.registerProvider).not.toHaveBeenCalled();
    await user.clear(emergency);
    await user.type(emergency, '5551234567');
    await user.click(toggle);
    expect(screen.queryByLabelText('Emergency contact number')).toBeNull();
    await user.click(submit);
    await waitFor(() => expect(authApi.registerProvider).toHaveBeenCalledWith(expect.objectContaining({
      emergency_services_available: false,
      emergency_contact_number: null,
    })));
  });
});

describe('provider signup postal lookup', () => {
  it('requires explicit selection for a unique match and normalizes the selected country', async () => {
    const user = userEvent.setup();
    vi.mocked(authApi.lookupProviderPostalCode).mockResolvedValue({
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
    render(createElement(MemoryRouter, null, createElement(ProviderSignupPage)));
    const postal = await screen.findByLabelText('Pincode / postal code');
    await user.type(postal, '110001');
    const candidate = await screen.findByRole('button', { name: 'New Delhi, Delhi, India' });
    expect(screen.getByTestId('signup-location-values').textContent).toBe('||');
    expect(screen.getByText('Choose a place below to fill your location.')).toBeTruthy();

    await user.click(candidate);
    expect(screen.getByTestId('signup-location-values').textContent).toBe('India|Delhi|New Delhi');
    expect(screen.getByText('Location filled. You can correct it below.')).toBeTruthy();
  });

  it('does not show a delayed lookup result after manual location correction', async () => {
    const user = userEvent.setup();
    let resolveLookup: ((result: {
      status: 'match';
      candidates: Array<{
        country: string; country_code?: string; state_province: string; city: string;
        postal_code: string; display_name: string;
      }>;
    }) => void) | null = null;
    vi.mocked(authApi.lookupProviderPostalCode).mockImplementationOnce(() => new Promise((resolve) => {
      resolveLookup = resolve;
    }));
    render(createElement(MemoryRouter, null, createElement(ProviderSignupPage)));
    await user.type(await screen.findByLabelText('Pincode / postal code'), '90210');
    await waitFor(() => expect(authApi.lookupProviderPostalCode).toHaveBeenCalled());
    await user.click(screen.getByRole('button', { name: 'Choose test location' }));

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
    expect(screen.getByTestId('signup-location-values').textContent).toBe('Canada|Alberta|Calgary');
  });

  it('skips short postal queries and gives manual-entry feedback when lookup fails', async () => {
    const user = userEvent.setup();
    render(createElement(MemoryRouter, null, createElement(ProviderSignupPage)));
    const postal = await screen.findByLabelText('Pincode / postal code');
    await user.type(postal, '123');
    expect(authApi.lookupProviderPostalCode).not.toHaveBeenCalled();

    vi.mocked(authApi.lookupProviderPostalCode).mockRejectedValueOnce(new Error('offline'));
    await user.type(postal, '4');
    expect(await screen.findByText('Lookup is unavailable. Enter the location manually.')).toBeTruthy();
  });
});

describe('public provider signup bulk options', () => {
  for (const emailSent of [true, false]) {
  it(`submits selected options and offers input-free resend when delivery ${emailSent ? 'succeeds' : 'fails'}`, async () => {
    const user = userEvent.setup();
    vi.mocked(authApi.registerProvider).mockResolvedValue({ email_sent: emailSent, message: '' });
    render(createElement(MemoryRouter, null, createElement(ProviderSignupPage)));
    const specs = await screen.findByRole('button', { name: /Specializations/ });
    await user.click(specs);
    await user.type(screen.getByRole('searchbox', { name: 'Search specializations' }), 'Dental');
    await user.click(screen.getByRole('button', { name: 'Select all' }));
    expect(specs.textContent).toContain('2 selected');
    await user.clear(screen.getByRole('searchbox', { name: 'Search specializations' }));
    await user.click(screen.getByRole('option', { name: 'Emergency care' }));
    await user.type(screen.getByRole('searchbox', { name: 'Search specializations' }), 'Dental');
    await user.click(screen.getByRole('button', { name: 'Clear all' }));
    expect(specs.textContent).toContain('1 selected');
    expect(screen.getByRole('button', { name: 'Remove Emergency care' })).toBeTruthy();
    await user.clear(screen.getByRole('searchbox', { name: 'Search specializations' }));
    await user.click(screen.getByRole('option', { name: 'Dental care' }));
    await user.click(specs);

    const langs = screen.getByRole('button', { name: 'Languages' });
    await user.click(langs);
    await user.click(screen.getByRole('button', { name: 'Select all' }));
    expect(langs.textContent).toContain('3 selected');
    await user.type(screen.getByRole('searchbox', { name: 'Search languages' }), 'en');
    // "en" matches English (name/code) and French (name), but not German.
    await user.click(screen.getByRole('button', { name: 'Clear all' }));
    expect(langs.textContent).toContain('1 selected');
    await user.click(screen.getByRole('option', { name: /English/ }));
    await user.click(langs);

    await user.type(screen.getByLabelText('Provider or practice name'), 'Equine Clinic');
    await user.type(screen.getByLabelText('First name'), 'Amina');
    await user.type(screen.getByLabelText('Last name'), 'Vet');
    await user.type(screen.getByLabelText('Email address'), 'amina@example.com');
    await user.type(screen.getByLabelText('Mobile number'), '5551234567');
    await user.type(screen.getByLabelText('Professional title'), 'Veterinarian');
    await user.type(screen.getByLabelText('Years of experience'), '8');
    await user.type(screen.getByLabelText('Pincode / postal code'), 'T2P 1J9');
    await user.click(screen.getByRole('button', { name: 'Choose test location' }));
    await user.type(screen.getByLabelText('Address'), '42 Stable Road');
    await user.type(screen.getByLabelText('Password', { exact: true }), 'HorseCare2026');
    await user.type(screen.getByLabelText('Confirm password'), 'HorseCare2026');
    await user.click(document.getElementById('provider-accept-terms')!);
    await user.click(document.getElementById('provider-accept-privacy')!);
    await user.click(screen.getByRole('button', { name: 'Submit provider application' }));
    await waitFor(() => expect(authApi.registerProvider).toHaveBeenCalledWith(expect.objectContaining({
      specialization_ids: ['spec-c', 'spec-a'],
      language_ids: ['lang-de', 'lang-en'],
    })));
    expect(await screen.findByRole('heading', { name: emailSent ? 'Check your inbox' : 'Application saved' })).toBeTruthy();
    expect(screen.queryByRole('textbox')).toBeNull();
    vi.mocked(authApi.resendVerification).mockResolvedValue({ message: 'If this email belongs to an unverified account, a verification link will be sent when available.' });
    await user.click(screen.getByRole('button', { name: 'Request a new verification link' }));
    await waitFor(() => expect(authApi.resendVerification).toHaveBeenCalledWith('amina@example.com'));
  });
  }
});