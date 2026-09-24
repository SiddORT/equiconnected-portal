import { afterEach, describe, expect, it, vi } from 'vitest';
import { createElement } from 'react';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import type { RegistrationRequest } from '@/types';
import { SignupPage, validateSignup } from './SignupPage';
import * as authApi from '@/api/auth';

vi.mock('@/api/auth', () => ({ register: vi.fn(), resendVerification: vi.fn() }));
vi.mock('@/components/ui/LocationPicker', () => ({
  LocationPicker: ({ onChange }: { onChange: (value: object) => void }) =>
    createElement('button', { type: 'button', onClick: () => onChange({ country: 'Canada', state_province: 'Alberta', city: 'Calgary' }) }, 'Choose test location'),
}));
vi.mock('@/components/ui/PhoneInput', () => ({
  PhoneInput: ({ onNumberChange }: { onNumberChange: (value: string) => void }) =>
    createElement('input', { 'aria-label': 'Mobile number', onChange: (event: React.ChangeEvent<HTMLInputElement>) => onNumberChange(event.target.value) }),
}));
afterEach(() => { cleanup(); vi.resetAllMocks(); });

const validRegistration: RegistrationRequest = {
  first_name: 'Amina',
  last_name: 'Rider',
  email: 'amina@example.com',
  mobile_number: '50 123 4567',
  country: 'United States',
  state_province: 'California',
  city: 'Los Angeles',
  password: 'HorseCare2026',
  password_confirmation: 'HorseCare2026',
  role: 'HORSE_OWNER',
  accept_terms: true,
  accept_privacy: true,
};

describe('signup location validation', () => {
  it('requires a state or province when the selected country provides one', () => {
    expect(validateSignup({ ...validRegistration, state_province: '' }).state_province).toBe(
      'Select a state or province'
    );
  });

  it('accepts a coherent country, state, and city selection', () => {
    expect(validateSignup(validRegistration)).toEqual({});
  });
});

describe('member signup confirmation', () => {
  for (const emailSent of [true, false]) {
    it(`resends to the registered address without another email field when delivery ${emailSent ? 'succeeds' : 'fails'}`, async () => {
      const user = userEvent.setup();
      vi.mocked(authApi.register).mockResolvedValue({ email_sent: emailSent, message: '' });
      vi.mocked(authApi.resendVerification).mockResolvedValue({ message: 'If this email belongs to an unverified account, a verification link will be sent when available.' });
      render(createElement(MemoryRouter, null, createElement(SignupPage)));
      await user.type(screen.getByLabelText('First name'), 'Amina');
      await user.type(screen.getByLabelText('Last name'), 'Rider');
      await user.type(screen.getByLabelText('Email address'), 'Amina@Example.com ');
      await user.type(screen.getByLabelText('Mobile number'), '5551234567');
      await user.click(screen.getByRole('button', { name: 'Choose test location' }));
      await user.type(screen.getByLabelText('Password', { exact: true }), 'HorseCare2026');
      await user.type(screen.getByLabelText('Confirm password'), 'HorseCare2026');
      await user.click(document.getElementById('accept-terms')!);
      await user.click(document.getElementById('accept-privacy')!);
      await user.click(screen.getByRole('button', { name: 'Create account' }));
      expect(await screen.findByRole('heading', { name: emailSent ? 'Check your inbox' : 'Account saved' })).toBeTruthy();
      expect(screen.queryByRole('textbox')).toBeNull();
      await user.click(screen.getByRole('button', { name: 'Request a new verification link' }));
      await waitFor(() => expect(authApi.resendVerification).toHaveBeenCalledWith('amina@example.com'));
      expect(screen.getByRole('status').textContent).toContain('If this email belongs');
    });
  }
});