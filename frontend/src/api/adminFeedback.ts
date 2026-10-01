import { apiClient } from './client';

export type PlatformFeedbackStatus = 'Pending' | 'In review' | 'Resolved' | 'Rejected';
export type PlatformFeedbackFilterStatus = PlatformFeedbackStatus | 'withdrawn';
export type PlatformFeedbackCategory =
  | 'Website / App'
  | 'Search & Matching'
  | 'Provider Experience'
  | 'Account / Profile'
  | 'Technical Issue'
  | 'Suggestion'
  | 'Other';

export interface PlatformFeedbackAction {
  id: string;
  actor_id: string | null;
  actor_name: string | null;
  actor_email: string;
  actor_type: string;
  action: string;
  from_status: PlatformFeedbackStatus | null;
  to_status: PlatformFeedbackStatus | null;
  version: number;
  content_snapshot: Record<string, unknown>;
  created_at: string;
}

export interface AdminPlatformFeedback {
  id: string;
  member_id: string | null;
  submitter_name: string;
  submitter_email: string;
  category: PlatformFeedbackCategory;
  subject: string | null;
  rating: number | null;
  message: string;
  status: PlatformFeedbackStatus;
  withdrawn_at: string | null;
  member_response: string | null;
  internal_note: string | null;
  version: number;
  submitted_at: string;
  updated_at: string;
  history?: PlatformFeedbackAction[];
}

export interface AdminPlatformFeedbackParams {
  q?: string;
  status?: PlatformFeedbackFilterStatus;
  category?: PlatformFeedbackCategory;
  page?: number;
  page_size?: number;
}

export interface AdminPlatformFeedbackPage {
  data: AdminPlatformFeedback[];
  meta: { page: number; page_size: number; total: number; total_pages: number };
}

export interface AdminPlatformFeedbackUpdate {
  expected_version: number;
  status: PlatformFeedbackStatus;
  member_response?: string | null;
  internal_note?: string | null;
}

export async function listAdminPlatformFeedback(
  params: AdminPlatformFeedbackParams = {},
): Promise<AdminPlatformFeedbackPage> {
  const { data } = await apiClient.get<AdminPlatformFeedbackPage>('/admin/feedback', { params });
  return data;
}

export async function getAdminPlatformFeedback(id: string): Promise<AdminPlatformFeedback> {
  const { data } = await apiClient.get<AdminPlatformFeedback>(`/admin/feedback/${id}`);
  return data;
}

export async function updateAdminPlatformFeedback(
  id: string,
  payload: AdminPlatformFeedbackUpdate,
): Promise<AdminPlatformFeedback> {
  const { data } = await apiClient.patch<AdminPlatformFeedback>(`/admin/feedback/${id}`, payload);
  return data;
}