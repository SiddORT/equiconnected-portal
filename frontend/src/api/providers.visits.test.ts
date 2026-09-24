import { describe, expect, it, vi } from 'vitest';
import { apiClient } from './client';
import { createProviderVisit, updateProviderVisit } from './providers';

vi.mock('./client', () => ({
  apiClient: {
    post: vi.fn(),
    patch: vi.fn(),
  },
}));

describe('admin doctor visit API', () => {
  const body = {
    location: {
      address_line_1: '42 Stable Road',
      city: 'Calgary',
      name: 'North paddock',
      state_province: 'Alberta',
      country: 'Canada',
      postal_code: 'T2P 1J9',
    },
    start_date: '2026-06-01',
    end_date: '2026-06-03',
  };

  it('posts a complete initial/future visit body and returns the provider response', async () => {
    vi.mocked(apiClient.post).mockResolvedValueOnce({ data: { id: 'provider-1', doctor_visits: [] } });
    await expect(createProviderVisit('provider-1', body)).resolves.toEqual({ id: 'provider-1', doctor_visits: [] });
    expect(apiClient.post).toHaveBeenCalledWith('/admin/providers/provider-1/visits', body);
  });

  it('patches only the selected upcoming visit with the same contract', async () => {
    vi.mocked(apiClient.patch).mockResolvedValueOnce({ data: { id: 'provider-1' } });
    await updateProviderVisit('provider-1', 'visit-7', body);
    expect(apiClient.patch).toHaveBeenCalledWith('/admin/providers/provider-1/visits/visit-7', body);
  });
});