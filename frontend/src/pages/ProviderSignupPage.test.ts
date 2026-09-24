import { describe, expect, it, vi, afterEach } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
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
  lookupProviderPostalCode: vi.fn().mockResolvedValue({ status: 'no_match', candidates: [] }),
}));
vi.mock('@/components/ui/LocationPicker', () => ({
  LocationPicker: ({ onChange }: { onChange: (value: object) => void }) =>
    createElement('button', { type: 'button', onClick: () => onChange({ country: 'Canada', state_province: 'Alberta', city: 'Calgary' }) }, 'Choose test location'),
}));
vi.mock('@/components/ui/PhoneInput', () => ({
  PhoneInput: ({ onNumberChange }: { onNumberChange: (value: string) => void }) =>
    createElement('input', { 'aria-label': 'Mobile number', onChange: (event: React.ChangeEvent<HTMLInputElement>) => onNumberChange(event.target.value) }),
}));

afterEach(() => { cleanup(); vi.clearAllMocks(); });

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

  it('requires an active specialization selection and professional experience', () => {
    expect(validateProviderSignup({
      ...validApplication, specialization_ids: [], years_experience: null,
    })).toMatchObject({
      specialization_ids: 'Select at least one specialization',
      years_experience: 'Enter years of experience between 0 and 100',
    });
  });
});

describe('public provider signup bulk options', () => {
  it('selects, clears, and toggles filtered specializations and languages in the submitted IDs', async () => {
    const user = userEvent.setup();
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
  });
});