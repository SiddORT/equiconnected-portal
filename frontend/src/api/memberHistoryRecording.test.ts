import { afterEach, describe, expect, it, vi } from 'vitest';
import { historyFilters, recordMemberHistory } from './memberHistoryRecording';

const { post } = vi.hoisted(() => ({ post: vi.fn() }));
vi.mock('./client', () => ({ apiClient: { post } }));
afterEach(() => vi.resetAllMocks());

describe('member history recording', () => {
  it('retains supported applied filters but excludes coordinates and pagination', () => {
    const snapshot = historyFilters(new URLSearchParams('name=Vet&latitude=25.12345&longitude=55.12345&page=2&page_size=50&view=grid&emergency_only=true&region=Dubai'));
    expect(snapshot).toEqual({ name: 'Vet', region: 'Dubai', emergency_only: 'true' });
  });
  it('does not block browsing when recording is unavailable', async () => {
    post.mockRejectedValue(new Error('Unavailable'));
    await expect(recordMemberHistory({ event_key: 'search:one', type: 'search', filters: { name: 'Vet' } })).resolves.toBeUndefined();
  });
  it('keeps caller event identities stable for server retry deduplication', async () => {
    post.mockResolvedValue({});
    const event = { event_key: 'provider:one', type: 'provider' as const, provider_id: 'provider-id' };
    await recordMemberHistory(event);
    await recordMemberHistory(event);
    expect(post.mock.calls[0]).toEqual(post.mock.calls[1]);
  });
});