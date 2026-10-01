import { apiClient } from './client';

export type FeedbackCategory =
  | 'Website / App'
  | 'Search & Matching'
  | 'Provider Experience'
  | 'Account / Profile'
  | 'Technical Issue'
  | 'Suggestion'
  | 'Other';
export type ReviewStatus = 'PENDING' | 'PUBLISHED' | 'REJECTED' | 'HIDDEN';
export type FeedbackStatus = 'Pending' | 'In review' | 'Resolved' | 'Rejected';

export interface PlatformFeedback {
  id: string;
  category: FeedbackCategory;
  subject: string | null;
  rating: number | null;
  message: string;
  status: FeedbackStatus;
  member_response: string | null;
  submitted_at: string;
  updated_at: string;
  version: number;
  withdrawn_at: string | null;
}

export interface MemberReview {
  id: string;
  provider_id: string;
  provider_name: string;
  rating: number;
  comment: string;
  status: ReviewStatus;
  member_note: string | null;
  created_at: string;
  updated_at: string;
  version: number;
}

export type MemberHistoryEntry =
  | {
      id: string;
      event_key: string;
      type: 'search';
      occurred_at: string;
      filters: Record<string, string | boolean | number | null>;
      provider_id: null;
      provider_name: null;
      provider_available: null;
    }
  | {
      id: string;
      event_key: string;
      type: 'provider';
      occurred_at: string;
      filters: null;
      provider_id: string;
      provider_name: string;
      provider_available: boolean;
    };

export interface MemberFeedbackPage<T> {
  data: T[];
  meta: { page: number; page_size: number; total: number; total_pages: number };
}

export interface FeedbackPayload {
  category: FeedbackCategory;
  subject: string | null;
  rating: number | null;
  message: string;
}

export async function submitPlatformFeedback(payload: FeedbackPayload, idempotencyKey: string): Promise<PlatformFeedback> {
  const { data } = await apiClient.post<PlatformFeedback>('/member/feedback', { ...payload, idempotency_key: idempotencyKey });
  return data;
}

export async function listMemberFeedback(page = 1): Promise<MemberFeedbackPage<PlatformFeedback>> {
  const { data } = await apiClient.get<MemberFeedbackPage<PlatformFeedback>>('/member/feedback', { params: { page, page_size: 6 } });
  return data;
}

export async function updateMemberFeedback(id: string, version: number, payload: Partial<FeedbackPayload>): Promise<PlatformFeedback> {
  const { data } = await apiClient.patch<PlatformFeedback>(`/member/feedback/${id}`, { ...payload, expected_version: version });
  return data;
}

export async function withdrawMemberFeedback(id: string, version: number): Promise<void> {
  await apiClient.delete(`/member/feedback/${id}`, { params: { expected_version: version } });
}

export async function listMemberReviews(page = 1): Promise<MemberFeedbackPage<MemberReview>> {
  const { data } = await apiClient.get<MemberFeedbackPage<MemberReview>>('/member/reviews', { params: { page, page_size: 6 } });
  return data;
}

export async function updateMemberReview(id: string, version: number, payload: { rating: number; comment: string }): Promise<MemberReview> {
  const { data } = await apiClient.put<MemberReview>(`/member/reviews/${id}`, { ...payload, expected_version: version });
  return data;
}

export async function deleteMemberReview(id: string, version: number): Promise<void> {
  await apiClient.delete(`/member/reviews/${id}`, { params: { expected_version: version } });
}

export async function listMemberHistory(page = 1, pageSize = 10): Promise<MemberFeedbackPage<MemberHistoryEntry>> {
  const { data } = await apiClient.get<MemberFeedbackPage<MemberHistoryEntry>>('/member/history', { params: { page, page_size: pageSize } });
  return data;
}

export async function getRecentMemberHistory(): Promise<MemberHistoryEntry[]> {
  const { data } = await apiClient.get<MemberHistoryEntry[]>('/member/history/recent');
  return data;
}

export async function getMemberFeedbackCounts(): Promise<{ total: number; pending: number; in_review: number; resolved: number; rejected: number }> {
  const { data } = await apiClient.get('/member/feedback/counts');
  return data;
}

export async function getMemberReviewCounts(): Promise<Record<string, number>> {
  const { data } = await apiClient.get<Record<string, number>>('/member/reviews/counts');
  return data;
}