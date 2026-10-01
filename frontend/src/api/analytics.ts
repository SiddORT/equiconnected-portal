import { apiClient } from './client';
import type {
  AnalyticsBreakdowns, AnalyticsDomain, AnalyticsFilters, AnalyticsQuery,
  AnalyticsSeries, AnalyticsSummary, ProviderRankingResponse,
} from '@/types/analytics';

export async function getAnalyticsSummary(params: AnalyticsFilters): Promise<AnalyticsSummary> {
  const { data } = await apiClient.get<AnalyticsSummary>('/admin/analytics/summary', { params });
  return data;
}

export async function getAnalyticsSeries(metric: string, params: AnalyticsFilters): Promise<AnalyticsSeries> {
  const { data } = await apiClient.get<AnalyticsSeries>('/admin/analytics/series', { params: { ...params, metric } });
  return data;
}

export async function getAnalyticsBreakdowns(domain: AnalyticsDomain, params: AnalyticsFilters): Promise<AnalyticsBreakdowns> {
  const { data } = await apiClient.get<AnalyticsBreakdowns>('/admin/analytics/breakdowns', { params: { ...params, domain } });
  return data;
}

export async function getProviderRanking(params: AnalyticsQuery): Promise<ProviderRankingResponse> {
  const { data } = await apiClient.get<ProviderRankingResponse>('/admin/analytics/provider-ranking', { params });
  return data;
}

export async function exportAnalytics(params: AnalyticsQuery): Promise<void> {
  const response = await apiClient.get('/admin/analytics/export', { params, responseType: 'blob' });
  const url = URL.createObjectURL(response.data as Blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `analytics-${params.dataset ?? params.domain ?? params.metric ?? 'report'}-${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}