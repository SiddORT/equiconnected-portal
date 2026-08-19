/**
 * Doctor API client — /api/v1/admin/doctors
 */
import { apiClient } from './client';
import type {
  DoctorCreate,
  DoctorListItem,
  DoctorOrganizationCreate,
  DoctorOrganizationUpdate,
  DoctorResponse,
  DoctorUpdate,
  PaginatedResponse,
  QualificationCreate,
  QualificationResponse,
  QualificationUpdate,
} from '@/types';

// ── List / Detail ─────────────────────────────────────────────────────────────

export async function listDoctors(params: {
  search?: string;
  specialization_id?: string;
  organization_id?: string;
  visit_stability?: string;
  status?: string;
  publication_status?: string;
  page?: number;
  page_size?: number;
}): Promise<PaginatedResponse<DoctorListItem>> {
  const { data } = await apiClient.get<PaginatedResponse<DoctorListItem>>(
    '/admin/doctors',
    { params }
  );
  return data;
}

export async function getDoctor(id: string): Promise<DoctorResponse> {
  const { data } = await apiClient.get<DoctorResponse>(`/admin/doctors/${id}`);
  return data;
}

// ── Create / Update ───────────────────────────────────────────────────────────

export async function createDoctor(body: DoctorCreate): Promise<DoctorResponse> {
  const { data } = await apiClient.post<DoctorResponse>('/admin/doctors', body);
  return data;
}

export async function updateDoctor(id: string, body: DoctorUpdate): Promise<DoctorResponse> {
  const { data } = await apiClient.patch<DoctorResponse>(`/admin/doctors/${id}`, body);
  return data;
}

export async function updateDoctorStatus(
  id: string,
  status: 'ACTIVE' | 'INACTIVE'
): Promise<DoctorResponse> {
  const { data } = await apiClient.patch<DoctorResponse>(`/admin/doctors/${id}/status`, { status });
  return data;
}

export async function updateDoctorPublication(
  id: string,
  publication_status: 'PUBLISHED' | 'UNPUBLISHED'
): Promise<DoctorResponse> {
  const { data } = await apiClient.patch<DoctorResponse>(`/admin/doctors/${id}/publication`, {
    publication_status,
  });
  return data;
}

// ── Specializations ───────────────────────────────────────────────────────────

export async function addDoctorSpecialization(
  id: string,
  specialization_id: string
): Promise<DoctorResponse> {
  const { data } = await apiClient.post<DoctorResponse>(
    `/admin/doctors/${id}/specializations`,
    { specialization_id }
  );
  return data;
}

export async function removeDoctorSpecialization(
  id: string,
  specId: string
): Promise<DoctorResponse> {
  const { data } = await apiClient.delete<DoctorResponse>(
    `/admin/doctors/${id}/specializations/${specId}`
  );
  return data;
}

// ── Qualifications ────────────────────────────────────────────────────────────

export async function addDoctorQualification(
  id: string,
  body: QualificationCreate
): Promise<QualificationResponse> {
  const { data } = await apiClient.post<QualificationResponse>(
    `/admin/doctors/${id}/qualifications`,
    body
  );
  return data;
}

export async function updateDoctorQualification(
  id: string,
  qualId: string,
  body: QualificationUpdate
): Promise<QualificationResponse> {
  const { data } = await apiClient.patch<QualificationResponse>(
    `/admin/doctors/${id}/qualifications/${qualId}`,
    body
  );
  return data;
}

export async function deleteDoctorQualification(id: string, qualId: string): Promise<void> {
  await apiClient.delete(`/admin/doctors/${id}/qualifications/${qualId}`);
}

// ── Organization relationships ─────────────────────────────────────────────────

export async function addDoctorOrganization(
  id: string,
  body: DoctorOrganizationCreate
): Promise<DoctorResponse> {
  const { data } = await apiClient.post<DoctorResponse>(
    `/admin/doctors/${id}/organizations`,
    body
  );
  return data;
}

export async function updateDoctorOrganization(
  id: string,
  relId: string,
  body: DoctorOrganizationUpdate
): Promise<DoctorResponse> {
  const { data } = await apiClient.patch<DoctorResponse>(
    `/admin/doctors/${id}/organizations/${relId}`,
    body
  );
  return data;
}

export async function removeDoctorOrganization(
  id: string,
  relId: string
): Promise<DoctorResponse> {
  const { data } = await apiClient.delete<DoctorResponse>(
    `/admin/doctors/${id}/organizations/${relId}`
  );
  return data;
}
