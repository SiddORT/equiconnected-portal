/**
 * Shared TypeScript types for the EquiConnected Portal.
 * These mirror the backend Pydantic schemas.
 */

// ── Auth ─────────────────────────────────────────────────────────────────────

export interface UserProfile {
  id: string;
  email: string;
  first_name: string | null;
  last_name: string | null;
  full_name: string;
  role: string;
  is_active: boolean;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: UserProfile;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

// ── API Error ─────────────────────────────────────────────────────────────────

export interface ApiErrorDetail {
  code: string;
  message: string;
  field?: string | null;
}

export interface ApiErrorResponse {
  error?: ApiErrorDetail;
  detail?: ApiErrorDetail | string;
}

// ── Admin Dashboard ───────────────────────────────────────────────────────────

export interface AuditEvent {
  id: string;
  action: string;
  user_id: string | null;
  created_at: string;
}

export interface DashboardStats {
  total_users: number;
  recent_audit_events: AuditEvent[];
}

// ── Pagination ────────────────────────────────────────────────────────────────

export interface PaginationMeta {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export interface PaginatedResponse<T> {
  data: T[];
  meta: PaginationMeta;
}

// ── Common ────────────────────────────────────────────────────────────────────

export type LoadingState = 'idle' | 'loading' | 'success' | 'error';

// ── Specializations ───────────────────────────────────────────────────────────

export interface Specialization {
  id: string;
  name: string;
  description: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface SpecializationCreate {
  name: string;
  description?: string | null;
  is_active?: boolean;
}

export interface SpecializationUpdate {
  name?: string;
  description?: string | null;
}

// ── CSV import/export ─────────────────────────────────────────────────────────

export type ImportRowState = 'valid' | 'duplicate' | 'invalid';

export interface ImportRowPreview {
  row_num: number;
  name: string;
  description: string | null;
  status: string;
  state: ImportRowState;
  reason: string | null;
}

export interface ImportPreviewResponse {
  total: number;
  valid: number;
  duplicate: number;
  invalid: number;
  rows: ImportRowPreview[];
}

export interface ImportResult {
  imported: number;
  skipped: number;
  errors: number;
  row_details: ImportRowPreview[];
}

// ── Providers ─────────────────────────────────────────────────────────────────

export type ProviderType = 'HOSPITAL' | 'CLINIC' | 'DOCTOR';
export type VisitStability = 'STABLE_VISIT' | 'NOT_STABLE_VISIT';
export type ProviderStatus = 'ACTIVE' | 'INACTIVE';
export type PublicationStatus = 'UNPUBLISHED' | 'PUBLISHED';

export interface ProviderListItem {
  id: string;
  provider_type: ProviderType;
  name: string;
  email: string | null;
  phone: string | null;
  visit_stability: VisitStability;
  status: ProviderStatus;
  publication_status: PublicationStatus;
  created_at: string;
  updated_at: string;
}

export interface ProviderSpecializationBrief {
  id: string;
  name: string;
  is_active: boolean;
}

export interface ProviderLocation {
  id: string;
  provider_id: string;
  address_line_1: string;
  address_line_2: string | null;
  city: string;
  state_province: string | null;
  country: string | null;
  postal_code: string | null;
  latitude: string | number | null;
  longitude: string | number | null;
  is_primary: boolean;
  created_at: string;
  updated_at: string;
}

export interface ProviderPhoto {
  id: string;
  provider_id: string;
  storage_reference: string;
  alt_text: string | null;
  caption: string | null;
  display_order: number;
  is_thumbnail: boolean;
  created_at: string;
  updated_at: string;
}

export interface ProviderPhone {
  id: string;
  provider_id: string;
  country_code: string;
  number: string;
  is_primary: boolean;
  created_at: string;
  updated_at: string;
}

export interface ProviderPhoneCreate {
  country_code: string;
  number: string;
  is_primary?: boolean;
}

export interface ProviderEmail {
  id: string;
  provider_id: string;
  email: string;
  is_primary: boolean;
  created_at: string;
  updated_at: string;
}

export interface ProviderEmailCreate {
  email: string;
  is_primary?: boolean;
}

export interface Provider extends ProviderListItem {
  description: string | null;
  website: string | null;
  specializations: ProviderSpecializationBrief[];
  locations: ProviderLocation[];
  photos: ProviderPhoto[];
  phones: ProviderPhone[];
  emails: ProviderEmail[];
}

export interface ProviderLocationCreate {
  address_line_1: string;
  address_line_2?: string | null;
  city: string;
  state_province?: string | null;
  country?: string | null;
  postal_code?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  is_primary?: boolean;
}

export type ProviderLocationUpdate = Partial<ProviderLocationCreate>;

export interface ProviderCreate {
  provider_type: ProviderType;
  name: string;
  visit_stability: VisitStability;
  description?: string | null;
  email?: string | null;
  phone?: string | null;
  website?: string | null;
  status?: ProviderStatus;
  publication_status?: PublicationStatus;
  specialization_ids?: string[];
  primary_location?: ProviderLocationCreate | null;
  phones?: ProviderPhoneCreate[];
  emails?: ProviderEmailCreate[];
}

export interface ProviderUpdate {
  provider_type?: ProviderType;
  name?: string;
  description?: string | null;
  email?: string | null;
  phone?: string | null;
  website?: string | null;
  visit_stability?: VisitStability;
}

export interface ProviderPhotoCreate {
  storage_reference: string;
  alt_text?: string | null;
  caption?: string | null;
  display_order?: number;
  is_thumbnail?: boolean;
}

export interface ProviderPhotoUpdate {
  storage_reference?: string;
  alt_text?: string | null;
  caption?: string | null;
  display_order?: number;
}

export interface ProviderListParams {
  search?: string;
  provider_type?: ProviderType;
  visit_stability?: VisitStability;
  status?: ProviderStatus;
  publication_status?: PublicationStatus;
  page?: number;
  page_size?: number;
}
