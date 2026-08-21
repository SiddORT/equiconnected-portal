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

export type PublicRoleSelection = 'HORSE_OWNER' | 'STABLE_MANAGER' | 'BOTH';

export interface RegistrationRequest {
  first_name: string;
  last_name: string;
  email: string;
  mobile_number: string;
  country: string;
  city: string;
  password: string;
  password_confirmation: string;
  role: PublicRoleSelection;
  accept_terms: boolean;
  accept_privacy: boolean;
}

export interface MessageResponse {
  message: string;
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

export interface ProviderCounts {
  hospitals: number;
  clinics: number;
  doctors: number;
}

export interface InvitationCounts {
  sent: number;
  accepted: number;
  rejected: number;
}

export interface DailyVisit {
  date: string;
  count: number;
}

export interface LocationMarker {
  location_id: string;
  provider_id: string;
  provider_name: string;
  provider_type: 'HOSPITAL' | 'CLINIC' | 'DOCTOR';
  location_name: string | null;
  address: string;
  city: string;
  latitude: number;
  longitude: number;
  is_primary: boolean;
}

export interface DashboardStats {
  total_users: number;
  active_providers: number;
  provider_counts: ProviderCounts;
  invitation_counts: InvitationCounts;
  visitor_visits: DailyVisit[];
  location_markers: LocationMarker[];
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

// ── Activity logs ────────────────────────────────────────────────────────────

export interface AuditActor {
  id: string | null;
  name: string;
  email: string | null;
  kind: 'admin' | 'system' | 'public_invitation' | string;
}

export interface AuditChange {
  field: string;
  before: unknown;
  after: unknown;
}

export interface ActivityLog {
  id: string;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  actor: AuditActor;
  created_at: string;
  summary: string;
  changes: AuditChange[];
  metadata: Record<string, unknown>;
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
  thumbnail_url: string | null;
}

export interface ProviderSpecializationBrief {
  id: string;
  name: string;
  is_active: boolean;
}

export interface ProviderLocation {
  id: string;
  provider_id: string;
  name: string | null;
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

export interface DoctorProfileInfo {
  professional_title: string | null;
  biography: string | null;
  years_experience: number | null;
  experience_description: string | null;
}
export interface Provider extends ProviderListItem {
  doctor_profile: DoctorProfileInfo | null;
  description: string | null;
  website: string | null;
  specializations: ProviderSpecializationBrief[];
  locations: ProviderLocation[];
  photos: ProviderPhoto[];
  phones: ProviderPhone[];
  emails: ProviderEmail[];
}

export interface ProviderLocationCreate {
  name?: string | null;
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
  professional_title?: string | null;
  biography?: string | null;
  years_experience?: number | null;
  experience_description?: string | null;
}

export interface ProviderUpdate {
  provider_type?: ProviderType;
  name?: string;
  description?: string | null;
  email?: string | null;
  phone?: string | null;
  website?: string | null;
  visit_stability?: VisitStability;
  professional_title?: string | null;
  biography?: string | null;
  years_experience?: number | null;
  experience_description?: string | null;
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

// ── Provider invitations ──────────────────────────────────────────────────────

export type InvitationStatus = 'PENDING' | 'ACCEPTED' | 'EXPIRED' | 'CANCELLED' | 'COMPLETED';

export interface Invitation {
  id: string;
  provider_id: string | null;
  provider_name?: string | null;
  provider_type: ProviderType;
  recipient_email: string;
  status: InvitationStatus;
  expires_at: string;
  sent_at: string;
  accepted_at: string | null;
  completed_at: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
  /** Present only when an API implementation safely elects to expose a link. */
  is_new_provider?: boolean;
  invitation_url?: string | null;
}

export interface InvitationCreate {
  recipient_email: string;
  provider_type: ProviderType;
  provider_name?: string | null;
  provider_id?: string | null;
}

export interface InvitationListParams {
  search?: string;
  status?: InvitationStatus;
  provider_type?: ProviderType;
  date_from?: string;
  date_to?: string;
  page?: number;
  page_size?: number;
}

// ── Doctor domain — re-exported for convenient single-import ─────────────────
export type {
  DoctorOrganizationStatus,
  SpecBrief,
  OrgBrief,
  QualificationResponse,
  QualificationCreate,
  QualificationUpdate,
  DoctorOrgResponse,
  DoctorOrganizationCreate,
  DoctorOrganizationUpdate,
  DoctorListItem,
  DoctorResponse,
  DoctorCreate,
  DoctorUpdate,
} from './doctor';

// ── Public invitation domain — re-exported for convenient single-import ──────
export type {
  DraftLocation,
  DraftPhone,
  DraftEmail,
  DraftPhoto,
  InvitationDraftProvider,
  InvitationTokenData,
  InvitationDraftPayload,
  InvitationSpecialization,
  OrgSearchResult,
  OrgSuggestion,
  OrgRequestCreatePayload,
  OrgRequestResult,
} from './invitation';
