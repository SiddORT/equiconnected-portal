/**
 * Specializations API client functions.
 */
import { apiClient } from './client';
import { filenameFromDisposition, triggerCsvDownload } from '@/utils/csvExport';
import type {
  ImportPreviewResponse,
  ImportResult,
  ImportRowPreview,
  PaginatedResponse,
  Specialization,
  SpecializationCreate,
  SpecializationUpdate,
} from '@/types';

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

// ── CSV import/export ─────────────────────────────────────────────────────────

export async function exportSpecializations(params?: {
  search?: string;
  is_active?: boolean;
}): Promise<void> {
  const response = await apiClient.get('/admin/specializations/export', {
    params,
    responseType: 'blob',
  });
  const fallback = `equiconnected-specializations-${new Date().toISOString().slice(0, 10)}.csv`;
  const filename = filenameFromDisposition(response.headers['content-disposition'], fallback);
  triggerCsvDownload(response.data as Blob, filename);
}

export async function downloadImportTemplate(): Promise<void> {
  const response = await apiClient.get('/admin/specializations/import/template', {
    responseType: 'blob',
  });
  const filename = filenameFromDisposition(
    response.headers['content-disposition'],
    'equiconnected-specializations-template.csv'
  );
  triggerCsvDownload(response.data as Blob, filename);
}

export async function previewImport(file: File): Promise<ImportPreviewResponse> {
  const form = new FormData();
  form.append('file', file);
  const { data } = await apiClient.post<ImportPreviewResponse>(
    '/admin/specializations/import/preview',
    form,
    { headers: { 'Content-Type': 'multipart/form-data' } }
  );
  return data;
}

export async function confirmImport(rows: ImportRowPreview[]): Promise<ImportResult> {
  const { data } = await apiClient.post<ImportResult>('/admin/specializations/import', { rows });
  return data;
}

export async function setSpecializationStatus(id: string, is_active: boolean): Promise<Specialization> {
  const { data } = await apiClient.patch<Specialization>(
    `/admin/specializations/${id}/status`,
    { is_active }
  );
  return data;
}
