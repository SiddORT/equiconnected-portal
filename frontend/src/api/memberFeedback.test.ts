import { afterEach, describe, expect, it, vi } from 'vitest';
import { apiClient } from './client';
import { deleteMemberReview, getRecentMemberHistory, submitPlatformFeedback, withdrawMemberFeedback } from './memberFeedback';

vi.mock('./client', () => ({
  apiClient: {
    post: vi.fn(),
    get: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}));

afterEach(() => vi.resetAllMocks());

describe('member feedback API contracts', () => {
  it('posts the retry key with private feedback content', async () => {
    vi.mocked(apiClient.post).mockResolvedValueOnce({ data: { id: 'f-1' } });
    await submitPlatformFeedback({ category: 'Website / App', subject: null, rating: null, message: 'A private message' }, 'key-1');
    expect(apiClient.post).toHaveBeenCalledWith('/member/feedback', {
      category: 'Website / App', subject: null, rating: null, message: 'A private message', idempotency_key: 'key-1',
    });
  });

  it('uses the recent-history bare list response', async () => {
    const records = [{ id: 'h-1', event_key: 'visit:1', type: 'provider', provider_id: 'p-1', provider_name: 'Fieldside Equine', provider_available: true, filters: null, occurred_at: '2026-03-01T12:00:00Z' }];
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: records });
    expect(await getRecentMemberHistory()).toEqual(records);
    expect(apiClient.get).toHaveBeenCalledWith('/member/history/recent');
  });

  it('passes expected versions on member withdrawals and review deletions', async () => {
    vi.mocked(apiClient.delete).mockResolvedValue({ data: undefined });
    await withdrawMemberFeedback('f-2', 3);
    await deleteMemberReview('r-9', 7);
    expect(apiClient.delete).toHaveBeenNthCalledWith(1, '/member/feedback/f-2', { params: { expected_version: 3 } });
    expect(apiClient.delete).toHaveBeenNthCalledWith(2, '/member/reviews/r-9', { params: { expected_version: 7 } });
  });
});