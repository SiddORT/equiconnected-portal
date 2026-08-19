/**
 * Public provider-invitation types — mirror backend schemas/invitation.py
 * and schemas/organization_request.py (public side).
 */
import type { ProviderType, VisitStability } from './index';

// ── Draft provider payload (token endpoints) ─────────────────────────────────

export interface DraftLocation {
  name?: string | null;
  address_line_1: string;
  address_line_2?: string | null;
  city: string;
  state_province?: string | null;
  country?: string | null;
  postal_code?: string | null;
  latitude?: number | string | null;
  longitude?: number | string | null;
  is_primary?: boolean;
}

export interface DraftPhone {
  country_code: string;
  number: string;
  is_primary?: boolean;
}

export interface DraftEmail {
  email: string;
  is_primary?: boolean;
}

export interface DraftPhoto {
  storage_reference: string;
  alt_text?: string | null;
  caption?: string | null;
  display_order?: number;
  is_thumbnail?: boolean;
}

/** Provider snapshot returned by GET /provider/invitations/{token}. */
export interface InvitationDraftProvider {
  name: string;
  description: string | null;
  email: string | null;
  phone: string | null;
  website: string | null;
  visit_stability: VisitStability;
  status: string;
  specialization_ids: string[];
  locations: DraftLocation[];
  phones: DraftPhone[];
  emails: DraftEmail[];
  photos: DraftPhoto[];
  professional_title?: string | null;
  biography?: string | null;
  years_experience?: number | null;
  experience_description?: string | null;
}

export interface InvitationTokenData {
  id: string;
  provider_type: ProviderType;
  provider: InvitationDraftProvider;
}

/** Body for save-draft / submit token endpoints (fields optional for draft). */
export interface InvitationDraftPayload {
  name?: string;
  description?: string | null;
  website?: string | null;
  visit_stability?: VisitStability;
  specialization_ids?: string[];
  locations?: DraftLocation[];
  phones?: DraftPhone[];
  emails?: DraftEmail[];
  professional_title?: string | null;
  biography?: string | null;
  years_experience?: number | null;
  experience_description?: string | null;
  /**
   * Doctor submit only: final set of organization IDs to associate.
   * The server reconciles PENDING relationships atomically with the submit.
   */
  organization_ids?: string[];
}

// ── Organization search / association / requests ─────────────────────────────

export interface OrgSearchResult {
  id: string;
  name: string;
  provider_type: ProviderType;
  city: string | null;
}

export interface OrgSuggestion {
  id: string;
  name: string;
  type: ProviderType;
}

export interface OrgRequestCreatePayload {
  organization_name: string;
  organization_type: 'HOSPITAL' | 'CLINIC';
  contact_email?: string | null;
  location_hint?: string | null;
  confirm_no_match?: boolean;
}

export interface OrgRequestResult {
  id: string;
  doctor_provider_id: string;
  organization_name: string;
  organization_type: ProviderType;
  contact_email: string | null;
  location_hint: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface InvitationSpecialization {
  id: string;
  name: string;
}
