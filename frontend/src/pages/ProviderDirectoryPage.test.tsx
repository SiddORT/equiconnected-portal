import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import * as providersApi from '@/api/providers';
import { ProviderDirectoryPage } from './ProviderDirectoryPage';

vi.mock('@/api/providers', () => ({
  listMemberProviders: vi.fn(),
}));

const response = {
  data: [{
    id: 'provider-1',
    provider_type: 'CLINIC' as const,
    name: 'Austin Equine Clinic',
    description: 'Trusted care',
    website: null,
    email: null,
    phone: null,
    visit_stability: 'STABLE_VISIT' as const,
    location: { city: 'Austin', state_province: 'Texas', country: 'United States' },
    average_rating: 4.5,
    review_count: 3,
    distance_km: null,
  }],
  meta: { page: 1, page_size: 20, total: 1, total_pages: 1 },
};

const originalGeolocation = Object.getOwnPropertyDescriptor(navigator, 'geolocation');

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
  if (originalGeolocation) Object.defineProperty(navigator, 'geolocation', originalGeolocation);
});

describe('ProviderDirectoryPage', () => {
  it('loads URL-backed filters and keeps providers available when location access is unavailable', async () => {
    vi.mocked(providersApi.listMemberProviders).mockResolvedValue(response);
    Object.defineProperty(navigator, 'geolocation', { configurable: true, value: undefined });
    const user = userEvent.setup();

    render(
      <MemoryRouter initialEntries={['/providers?provider_type=CLINIC&minimum_rating=4']}>
        <ProviderDirectoryPage />
      </MemoryRouter>
    );

    await waitFor(() => expect(providersApi.listMemberProviders).toHaveBeenCalledWith(
      expect.objectContaining({ provider_type: 'CLINIC', minimum_rating: 4 })
    ));
    expect(await screen.findByRole('heading', { name: 'Austin Equine Clinic' })).toBeTruthy();

    await user.click(screen.getByRole('button', { name: 'Sort closest first' }));
    expect(await screen.findByText(/browser does not support location access/i)).toBeTruthy();
    expect(screen.getByRole('heading', { name: 'Austin Equine Clinic' })).toBeTruthy();
  });
});