import { afterEach, describe, expect, it, vi } from 'vitest';
import { apiClient } from './client';
import { listAdminReviews, updateAdminReview } from './reviews';

vi.mock('./client', () => ({
  apiClient: {
    get: vi.fn(),
    patch: vi.fn(),
  },
}));

afterEach(() => vi.resetAllMocks());

describe('admin review API', () => {
  it('uses only the backend-supported list filters', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: { data: [], meta: { page: 1, page_size: 25, total: 0, total_pages: 1 } } });
    const params = { status: 'PENDING' as const, provider_id: 'provider-1', page: 1, page_size: 25 };

    await listAdminReviews(params);

    expect(apiClient.get).toHaveBeenCalledWith('/admin/reviews', { params });
  });

  it('writes moderation changes to the status endpoint with the expected version', async () => {
    const payload = {
      status: 'PUBLISHED' as const,
      expected_version: 4,
      member_note: 'Thank you for sharing your experience.',
      internal_note: 'Reviewed against provider response.',
    };
    vi.mocked(apiClient.patch).mockResolvedValue({ data: { id: 'review-1' } });

    await updateAdminReview('review-1', payload);

    expect(apiClient.patch).toHaveBeenCalledWith('/admin/reviews/review-1/status', payload);
  });
});