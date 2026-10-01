export type AnalyticsPreset =
  | 'today' | 'yesterday' | 'last_7_days' | 'last_30_days'
  | 'this_month' | 'last_month' | 'all' | 'custom';
export type AnalyticsGrouping = 'daily' | 'weekly' | 'monthly';
export type AnalyticsDomain =
  | 'traffic' | 'registrations' | 'providers' | 'applications' | 'invitations'
  | 'reviews' | 'feedback' | 'enquiries' | 'subscribers';

export interface AnalyticsFilters {
  preset: AnalyticsPreset;
  date_from?: string;
  date_to?: string;
  group_by: AnalyticsGrouping;
  provider_type?: string;
  provider_status?: string;
  publication_status?: string;
  provider_id?: string;
  specialization_id?: string;
  provider_search?: string;
  country?: string;
  city?: string;
  member_role?: string;
  member_verified?: string;
  member_active?: string;
  application_status?: string;
  invitation_status?: string;
  review_status?: string;
  rating?: string;
  feedback_category?: string;
  feedback_status?: string;
  enquiry_type?: string;
  subscriber_type?: string;
}

export interface AnalyticsComparison {
  available: boolean;
  previous_value: number | null;
  change_percent: number | null;
  unavailable_reason?: string | null;
}

export interface AnalyticsCoverage {
  available: boolean;
  from?: string | null;
  through?: string | null;
  partial?: boolean;
  tracked_since?: string | null;
}

export interface AnalyticsMetric {
  key: string;
  label?: string;
  value: number | null;
  unit: string;
  basis: 'period' | 'current';
  available?: boolean;
  partial_coverage?: boolean;
  definition: string;
  comparison?: AnalyticsComparison | null;
  coverage?: AnalyticsCoverage | null;
}

export interface ProviderInventorySummary {
  total: number;
  status: Record<string, number>;
  type: Record<string, number>;
  publication: Record<string, number>;
  active: number;
  active_published: number;
}

export interface RegistrationCohortState {
  total: number;
  roles: { horse_owner: number; stable_manager: number; both: number };
  verified: Record<string, number>;
  active: Record<string, number>;
  role_assignments: Record<string, number>;
}

export type AnalyticsGroup = Record<string, unknown> | Array<Record<string, unknown>>;

export interface AnalyticsSection {
  metrics?: AnalyticsMetric[];
  coverage?: AnalyticsCoverage;
  inventory?: ProviderInventorySummary;
  cohort_current_state?: RegistrationCohortState;
  current_status?: AnalyticsGroup;
  submitted_cohort_status?: AnalyticsGroup;
  invitation_status?: AnalyticsGroup;
  invitation_cohort_status?: AnalyticsGroup;
  legacy_compatible_invitation_totals?: Record<string, unknown>;
  enquiry_types?: AnalyticsGroup;
  subscriber_types?: AnalyticsGroup;
  star_distribution?: AnalyticsGroup;
  retained_deleted_history?: number | Record<string, unknown>;
  categories?: AnalyticsGroup;
  [key: string]: unknown;
}

export interface AnalyticsSummary {
  timezone: string;
  period: { preset: AnalyticsPreset; date_from: string | null; date_to: string | null; group_by: AnalyticsGrouping };
  tracking_started_date?: string | null;
  coverage: Record<string, AnalyticsCoverage>;
  refreshed_at: string;
  sections: Record<string, AnalyticsSection>;
}

export interface AnalyticsPoint { bucket: string; value: number | null }
export interface AnalyticsSeries {
  metric: string;
  unit: string;
  timezone: string;
  period: AnalyticsSummary['period'];
  coverage: AnalyticsCoverage;
  available: boolean;
  partial_coverage: boolean;
  data: AnalyticsPoint[] | null;
}

export interface AnalyticsBreakdowns {
  domain: AnalyticsDomain;
  timezone: string;
  period: AnalyticsSummary['period'];
  coverage: AnalyticsCoverage;
  definitions?: Record<string, string>;
  groups: Record<string, AnalyticsGroup>;
}

export interface ProviderRankingRow {
  provider_id: string;
  name: string;
  provider_type: string;
  provider_status: string;
  publication_status: string;
  profile_views: number | null;
  profile_views_available?: boolean;
  review_submissions: number;
  average_rating: number | null;
  rating_count: number;
  saved_count: number;
}

export interface ProviderRankingResponse {
  data: ProviderRankingRow[];
  meta: { page: number; page_size: number; total: number; total_pages: number };
  period: AnalyticsSummary['period'];
  timezone: string;
  coverage: AnalyticsCoverage;
}

export interface AnalyticsQuery extends AnalyticsFilters {
  page?: number;
  page_size?: number;
  sort?: AnalyticsSort;
  sort_direction?: 'asc' | 'desc';
  metric?: string;
  domain?: AnalyticsDomain;
  dataset?: 'series' | 'breakdowns' | 'provider-ranking';
}

export type AnalyticsSort =
  | 'profile_views' | 'review_submissions' | 'average_rating'
  | 'rating_count' | 'saved_count' | 'name';