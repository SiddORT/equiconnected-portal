import { afterEach, describe, expect, it, vi } from 'vitest';
import { setupProviderPortalPassword } from './auth';
import { apiClient } from './client';

afterEach(() => vi.restoreAllMocks());

describe('provider setup response contract', () => {
  it.each(['<!doctype html><html>App</html>', {}, null, { message: '' }])('rejects a malformed HTTP 200 response', async (data) => {
    vi.spyOn(apiClient, 'post').mockResolvedValue({ data });
    await expect(setupProviderPortalPassword('synthetic-token', 'SyntheticSetup9', 'SyntheticSetup9'))
      .rejects.toThrow('Unexpected provider password setup response');
  });

  it('posts to the same-origin setup endpoint and accepts the API response', async () => {
    const post = vi.spyOn(apiClient, 'post').mockResolvedValue({ data: { message: 'Password set' } });
    await expect(setupProviderPortalPassword('synthetic-token', 'SyntheticSetup9', 'SyntheticSetup9'))
      .resolves.toEqual({ message: 'Password set' });
    expect(post).toHaveBeenCalledWith('/auth/provider-portal/setup-password', {
      token: 'synthetic-token', password: 'SyntheticSetup9', password_confirmation: 'SyntheticSetup9',
    });
    expect(apiClient.defaults.baseURL).toBe('/api/v1');
  });
});