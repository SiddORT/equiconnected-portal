/**
 * Admin API endpoint functions.
 */
import { apiClient } from './client';
import type {
  ActivityLog,
  AdminUser,
  AdminUserListParams,
  DashboardStats,
  EmailLogFilterMode,
  EmailDeliveryLog,
  PaginatedResponse,
  AdminProviderReview,
  ProviderApplication,
  ProviderApplicationListParams,
  ProviderProfileUpdate,
  ProviderProfileUpdateListParams,
  SystemSettings,
  SystemSettingsUpdate,
} from '@/types';

export async function getDashboardStats(): Promise<DashboardStats> {
  const { data } = await apiClient.get<DashboardStats>('/admin/dashboard/stats');
  return data;
}

export interface ActivityLogParams {
  date_from?: string;
  date_to?: string;
  page?: number;
  page_size?: number;
}

export async function getActivityLogs(
  params: ActivityLogParams
): Promise<PaginatedResponse<ActivityLog>> {
  const { data } = await apiClient.get<PaginatedResponse<ActivityLog>>(
    '/admin/activity-logs',
    { params }
  );
  return data;
}

export interface EmailDeliveryLogParams {
  filter_mode?: EmailLogFilterMode;
  date?: string;
  month?: number;
  year?: number;
  date_from?: string;
  date_to?: string;
  page?: number;
  page_size?: number;
}

export async function getEmailDeliveryLogs(
  params: EmailDeliveryLogParams
): Promise<PaginatedResponse<EmailDeliveryLog>> {
  const { data } = await apiClient.get<PaginatedResponse<EmailDeliveryLog>>(
    '/admin/email-logs',
    { params }
  );
  return data;
}

// ── Admin Users ────────────────────────────────────────────────────────────

export async function listAdminUsers(
  params?: AdminUserListParams
): Promise<PaginatedResponse<AdminUser>> {
  const { data } = await apiClient.get<PaginatedResponse<AdminUser>>(
    '/admin/users',
    { params }
  );
  return data;
}

export async function getAdminUser(id: string): Promise<AdminUser> {
  const { data } = await apiClient.get<AdminUser>(`/admin/users/${id}`);
  return data;
}

export async function listProviderApplications(
  params?: ProviderApplicationListParams
): Promise<PaginatedResponse<ProviderApplication>> {
  const { data } = await apiClient.get<PaginatedResponse<ProviderApplication>>(
    '/admin/provider-applications',
    { params }
  );
  return data;
}

export async function approveProviderApplication(id: string): Promise<ProviderApplication> {
  const { data } = await apiClient.post<ProviderApplication>(
    `/admin/provider-applications/${id}/approve`
  );
  return data;
}

export async function rejectProviderApplication(
  id: string,
  rejection_reason?: string
): Promise<ProviderApplication> {
  const { data } = await apiClient.post<ProviderApplication>(
    `/admin/provider-applications/${id}/reject`,
    rejection_reason ? { rejection_reason } : undefined
  );
  return data;
}

export async function listProviderProfileUpdates(
  params?: ProviderProfileUpdateListParams
): Promise<PaginatedResponse<ProviderProfileUpdate>> {
  const { data } = await apiClient.get<PaginatedResponse<ProviderProfileUpdate>>(
    '/admin/provider-profile-updates',
    { params }
  );
  return data;
}

export async function approveProviderProfileUpdate(id: string): Promise<ProviderProfileUpdate> {
  const { data } = await apiClient.post<ProviderProfileUpdate>(
    `/admin/provider-profile-updates/${id}/approve`
  );
  return data;
}

export async function rejectProviderProfileUpdate(
  id: string,
  rejection_reason?: string
): Promise<ProviderProfileUpdate> {
  const { data } = await apiClient.post<ProviderProfileUpdate>(
    `/admin/provider-profile-updates/${id}/reject`,
    rejection_reason ? { rejection_reason } : undefined
  );
  return data;
}

export interface AdminReviewParams {
  provider_id?: string;
  comment_visible?: boolean;
  page?: number;
  page_size?: number;
}

export async function listAdminReviews(
  params?: AdminReviewParams
): Promise<PaginatedResponse<AdminProviderReview>> {
  const { data } = await apiClient.get<PaginatedResponse<AdminProviderReview>>(
    '/admin/reviews',
    { params }
  );
  return data;
}

export async function setAdminReviewCommentVisibility(
  id: string,
  comment_visible: boolean
): Promise<AdminProviderReview> {
  const { data } = await apiClient.patch<AdminProviderReview>(
    `/admin/reviews/${id}/comment-visibility`,
    { comment_visible }
  );
  return data;
}

// ── System settings ────────────────────────────────────────────────────────

export async function getSystemSettings(): Promise<SystemSettings> {
  const { data } = await apiClient.get<SystemSettings>('/admin/system-settings');
  return data;
}

export async function updateSystemSettings(
  updates: SystemSettingsUpdate
): Promise<SystemSettings> {
  const { data } = await apiClient.patch<SystemSettings>('/admin/system-settings', updates);
  return data;
}
