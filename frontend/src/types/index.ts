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
