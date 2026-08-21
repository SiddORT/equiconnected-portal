/**
 * Admin API endpoint functions.
 */
import { apiClient } from './client';
import type { ActivityLog, DashboardStats, PaginatedResponse } from '@/types';

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
