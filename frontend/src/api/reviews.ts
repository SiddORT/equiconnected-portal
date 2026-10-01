import { apiClient } from './client';

export type ReviewStatus = 'PENDING' | 'PUBLISHED' | 'REJECTED' | 'HIDDEN';

export interface AdminReviewAction {
  id: string;
  actor_id: string | null;
  actor_name: string | null;
  actor_email: string;
  actor_type: string;
  action: string;
  from_status: ReviewStatus | null;
  to_status: ReviewStatus | null;
  version: number;
  content_snapshot: Record<string, unknown>;
  created_at: string;
}

export interface AdminReview {
  id: string;
  provider_id: string;
  provider_name: string;
  reviewer_id: string;
  reviewer_name: string;
  reviewer_email: string;
  rating: number;
  comment: string;
  comment_visible: boolean;
  status: ReviewStatus;
  member_note: string | null;
  internal_note: string | null;
  version: number;
  deleted_at: string | null;
  created_at: string;
  updated_at: string;
  history?: AdminReviewAction[];
}

export interface AdminReviewParams {
  provider_id?: string;
  status?: ReviewStatus;
  page?: number;
  page_size?: number;
}

export interface AdminReviewPage {
  data: AdminReview[];
  meta: { page: number; page_size: number; total: number; total_pages: number };
}

export interface AdminReviewUpdate {
  status: ReviewStatus;
  expected_version: number;
  member_note?: string | null;
  internal_note?: string | null;
}

export async function listAdminReviews(params: AdminReviewParams = {}): Promise<AdminReviewPage> {
  const { data } = await apiClient.get<AdminReviewPage>('/admin/reviews', { params });
  return data;
}

export async function getAdminReview(id: string): Promise<AdminReview> {
  const { data } = await apiClient.get<AdminReview>(`/admin/reviews/${id}`);
  return data;
}

export async function updateAdminReview(id: string, payload: AdminReviewUpdate): Promise<AdminReview> {
  const { data } = await apiClient.patch<AdminReview>(`/admin/reviews/${id}/status`, payload);
  return data;
}