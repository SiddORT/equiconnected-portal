/**
 * Specializations API client functions.
 */
import { apiClient } from './client';
import type { PaginatedResponse, PaginationMeta, Specialization, SpecializationCreate, SpecializationUpdate } from '@/types';

export async function listSpecializations(params?: {
  search?: string;
  is_active?: boolean;
  page?: number;
  page_size?: number;
}): Promise<PaginatedResponse<Specialization>> {
  const { data } = await apiClient.get<PaginatedResponse<Specialization>>(
    '/admin/specializations',
    { params }
  );
  return data;
}

export async function getSpecialization(id: string): Promise<Specialization> {
  const { data } = await apiClient.get<Specialization>(`/admin/specializations/${id}`);
  return data;
}

export async function createSpecialization(body: SpecializationCreate): Promise<Specialization> {
  const { data } = await apiClient.post<Specialization>('/admin/specializations', body);
  return data;
}

export async function updateSpecialization(id: string, body: SpecializationUpdate): Promise<Specialization> {
  const { data } = await apiClient.patch<Specialization>(`/admin/specializations/${id}`, body);
  return data;
}

export async function setSpecializationStatus(id: string, is_active: boolean): Promise<Specialization> {
  const { data } = await apiClient.patch<Specialization>(
    `/admin/specializations/${id}/status`,
    { is_active }
  );
  return data;
}
