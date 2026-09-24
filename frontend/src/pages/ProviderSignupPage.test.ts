import { describe, expect, it } from 'vitest';
import type { ProviderRegistrationRequest } from '@/types';
import { validateProviderSignup } from './ProviderSignupPage';

const validApplication: ProviderRegistrationRequest = {
  first_name: 'Amina',
  last_name: 'Veterinarian',
  email: 'amina@example.com',
  mobile_number: '50 123 4567',
  country: 'United States',
  state_province: 'California',
  city: 'Los Angeles',
  password: 'HorseCare2026',
  password_confirmation: 'HorseCare2026',
  role: 'PROVIDER',
  provider_type: 'CLINIC',
  provider_name: 'Amina Equine Clinic',
  visit_stability: 'STABLE_VISIT',
  professional_title: 'Equine veterinarian',
  specialization_ids: ['dc06ab91-4687-44cf-acef-47fa29ef80ad'],
  years_experience: 8,
  working_address: '12 Stable Lane',
  stable_visit: true,
  clinic_hospital_visit: true,
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