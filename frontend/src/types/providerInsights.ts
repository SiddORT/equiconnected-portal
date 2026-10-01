export type ProviderInsightsPreset = 'last_7_days' | 'last_30_days' | 'this_month' | 'custom';
export type CoverageStatus = 'full' | 'partial' | 'unavailable' | 'unknown';

export interface ProviderInsightMetric {
  value: number | null;
  definition: string;
  coverage: { status: CoverageStatus; from: string | null; note: string };
  comparison: { change_percent: number | null; previous_value: number | null; reason: string | null };
}

export interface ProviderInsights {
  provider_name: string;
  timezone: string;
  today: string;
  period: { date_from: string; date_to: string; preset: ProviderInsightsPreset };
  refreshed_at: string;
  metrics: {
    profile_views: ProviderInsightMetric;
    contact_clicks: ProviderInsightMetric;
    new_conversations: ProviderInsightMetric;
  };
  contact_breakdown: { phone: number | null; email: number | null; website: number | null };
  snapshot: {
    saved_members: number;
    rating_count: number;
    visible_review_count: number;
    average_rating: number | null;
  };
  trends: Array<{ date: string; profile_views: number | null; contact_clicks: number | null }>;
}