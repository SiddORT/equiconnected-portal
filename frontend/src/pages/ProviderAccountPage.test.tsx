import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import * as providersApi from '@/api/providers';
import { ProviderAccountPage } from './ProviderAccountPage';

vi.mock('@/api/providers', () => ({
  getProviderPortalProfile: vi.fn(),
  getProviderPortalSpecializations: vi.fn(),
  updateProviderPortalProfile: vi.fn(),
}));
vi.mock('@/api/client', () => ({
  getApiErrorCode: () => 'provider_portal_unavailable',
  extractErrorMessage: () => 'Provider portal unavailable',
}));
vi.mock('@/app/AuthContext', () => ({
  useAuth: () => ({
    user: { full_name: 'Approved Provider' },
    logout: vi.fn(),
  }),
}));

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

describe('ProviderAccountPage', () => {
  it('preserves the approved self-registered provider account view outside the invitation portal', async () => {
    vi.mocked(providersApi.getProviderPortalProfile).mockRejectedValue(new Error('not invitation-linked'));
    vi.mocked(providersApi.getProviderPortalSpecializations).mockResolvedValue([]);

    render(<MemoryRouter><ProviderAccountPage /></MemoryRouter>);

    expect(await screen.findByText('Your provider account is approved.')).toBeTruthy();
    expect(screen.getByText(/Your directory listing is staged/)).toBeTruthy();
    expect(screen.queryByText('Provider portal access is unavailable.')).toBeNull();
  });
});