/**
 * Doctor domain types — mirror backend schemas/doctor.py
 */
import type { ProviderStatus, PublicationStatus, ProviderType, VisitStability } from './index';

export type DoctorOrganizationStatus = 'ACTIVE' | 'INACTIVE';

// ── Brief sub-types ───────────────────────────────────────────────────────────

export interface SpecBrief {
  id: string;
  name: string;
  is_active: boolean;
}

export interface OrgBrief {
  id: string;
  provider_type: ProviderType;
  name: string;
  thumbnail_url: string | null;
}

// ── Qualification ─────────────────────────────────────────────────────────────

export interface QualificationResponse {
  id: string;
  provider_id: string;
  title: string;
  institution: string | null;
  year_obtained: number | null;
  description: string | null;
  display_order: number;
  created_at: string;
  updated_at: string;
}

export interface QualificationCreate {
  title: string;
  institution?: string | null;
  year_obtained?: number | null;
  description?: string | null;
  display_order?: number;
}

export interface QualificationUpdate {
  title?: string;
  institution?: string | null;
  year_obtained?: number | null;
  description?: string | null;
  display_order?: number;
}

// ── Organization relationship ─────────────────────────────────────────────────

export interface DoctorOrgResponse {
  id: string;
  organization_id: string;
  status: DoctorOrganizationStatus;
  is_primary: boolean;
  created_at: string;
  updated_at: string;
  organization: OrgBrief;
}

export interface DoctorOrganizationCreate {
  organization_id: string;
  status?: DoctorOrganizationStatus;
  is_primary?: boolean;
}

export interface DoctorOrganizationUpdate {
  status?: DoctorOrganizationStatus;
  is_primary?: boolean;
}

// ── Doctor list / detail ──────────────────────────────────────────────────────

export interface DoctorListItem {
  id: string;
  name: string;
  visit_stability: VisitStability;
  status: ProviderStatus;
  publication_status: PublicationStatus;
  created_at: string;
  updated_at: string;
  thumbnail_url: string | null;
  professional_title: string | null;
  specializations: SpecBrief[];
  primary_organization: OrgBrief | null;
  organization_count: number;
}

export interface DoctorResponse {
  id: string;
  name: string;
  visit_stability: VisitStability;
  status: ProviderStatus;
  publication_status: PublicationStatus;
  website: string | null;
  created_at: string;
  updated_at: string;
  thumbnail_url: string | null;
  professional_title: string | null;
  biography: string | null;
  years_experience: number | null;
  experience_description: string | null;
  specializations: SpecBrief[];
  qualifications: QualificationResponse[];
  organizations: DoctorOrgResponse[];
  phones: Array<{ id: string; country_code: string; number: string; is_primary: boolean }>;
  emails: Array<{ id: string; email: string; is_primary: boolean }>;
}

export interface DoctorCreate {
  name: string;
  visit_stability: VisitStability;
  status?: ProviderStatus;
  publication_status?: PublicationStatus;
  website?: string | null;
  professional_title?: string | null;
  biography?: string | null;
  years_experience?: number | null;
  experience_description?: string | null;
  specialization_ids?: string[];
  organization_ids?: string[];
  primary_organization_id?: string | null;
  phones?: Array<{ country_code: string; number: string; is_primary?: boolean }>;
  emails?: Array<{ email: string; is_primary?: boolean }>;
}

export interface DoctorUpdate {
  name?: string;
  visit_stability?: VisitStability;
  status?: ProviderStatus;
  publication_status?: PublicationStatus;
  website?: string | null;
  professional_title?: string | null;
  biography?: string | null;
  years_experience?: number | null;
  experience_description?: string | null;
}
