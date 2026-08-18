/**
 * Admin API endpoint functions.
 */
import { apiClient } from './client';
import type { DashboardStats } from '@/types';

export async function getDashboardStats(): Promise<DashboardStats> {
  const { data } = await apiClient.get<DashboardStats>('/admin/dashboard/stats');
  return data;
}
