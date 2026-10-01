import { apiClient } from './client';

// A route interaction keeps its key across retries and React's development
// effect replay. History must never retain browser coordinates.
const supported = [
  'name', 'visit_stability', 'specialization_id', 'region', 'provider_type',
  'minimum_rating', 'emergency_only', 'saved', 'sort',
];

export function historyFilters(params: URLSearchParams): Record<string, string> {
  return Object.fromEntries(supported.flatMap(key => {
    const value = params.get(key);
    return value ? [[key, value]] : [];
  }));
}

export async function recordMemberHistory(event: {
  event_key: string;
  type: 'search' | 'provider';
  filters?: Record<string, string>;
  provider_id?: string;
}): Promise<void> {
  try {
    await apiClient.post('/member/history', event);
    window.dispatchEvent(new Event('member-history-changed'));
  } catch {
    // History recording is best effort: browsing must remain available.
    // History readers have their own explicit loading/error presentation.
  }
}