import { afterEach, describe, expect, it, vi } from 'vitest';
import { apiClient } from './client';
import { listAdminPlatformFeedback, updateAdminPlatformFeedback } from './adminFeedback';

vi.mock('./client', () => ({
  apiClient: {
    get: vi.fn(),
    patch: vi.fn(),
  },
}));

afterEach(() => vi.resetAllMocks());

describe('admin platform feedback API', () => {
  it('uses q and the title-case backend status for list filtering', async () => {
    const params = { q: 'search', status: 'In review' as const, page: 2, page_size: 10 };
    vi.mocked(apiClient.get).mockResolvedValue({ data: { data: [], meta: { page: 2, page_size: 10, total: 0, total_pages: 1 } } });

    await listAdminPlatformFeedback(params);

    expect(apiClient.get).toHaveBeenCalledWith('/admin/feedback', { params });
  });

  it('updates processing state with an expected version', async () => {
    const payload = {
      expected_version: 3,
      status: 'Resolved' as const,
      member_response: 'We have fixed the issue.',
      internal_note: 'Resolved by support.',
    };
    vi.mocked(apiClient.patch).mockResolvedValue({ data: { id: 'feedback-1' } });

    await updateAdminPlatformFeedback('feedback-1', payload);

    expect(apiClient.patch).toHaveBeenCalledWith('/admin/feedback/feedback-1', payload);
  });
});