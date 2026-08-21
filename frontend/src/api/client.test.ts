import { describe, expect, it } from 'vitest';
import { extractErrorMessage, getApiErrorCode } from './client';

const registrationUnavailableError = {
  isAxiosError: true,
  response: {
    status: 503,
    data: {
      detail: {
        code: 'registration_unavailable',
        message: 'Internal role configuration is missing.',
      },
    },
  },
};

describe('registration availability errors', () => {
  it('keeps the public error message safe and understandable', () => {
    expect(getApiErrorCode(registrationUnavailableError)).toBe('registration_unavailable');
    expect(extractErrorMessage(registrationUnavailableError)).toBe(
      'Registration is temporarily unavailable. Please try again later.'
    );
  });
});