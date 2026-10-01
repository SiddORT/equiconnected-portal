import { apiClient } from '@/api/client';
import type { ProviderInsights, ProviderInsightsPreset } from '@/types/providerInsights';

export interface ProviderInsightsQuery {
  preset: ProviderInsightsPreset;
  date_from?: string;
  date_to?: string;
}

export async function getProviderInsights(params: ProviderInsightsQuery, signal?: AbortSignal): Promise<ProviderInsights> {
  const response = await apiClient.get<ProviderInsights>('/provider/portal/insights', { params, signal });
  return response.data;
}