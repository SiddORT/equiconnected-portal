/** Admin language master API client. */
import { apiClient } from './client';
import type { Language, LanguageCreate, LanguageUpdate, PaginatedResponse } from '@/types';

export async function listLanguages(params?: {
  search?: string; is_active?: boolean; page?: number; page_size?: number;
}): Promise<PaginatedResponse<Language>> {
  const { data } = await apiClient.get<PaginatedResponse<Language>>('/admin/languages', { params });
  return data;
}

export async function createLanguage(body: LanguageCreate): Promise<Language> {
  const { data } = await apiClient.post<Language>('/admin/languages', body);
  return data;
}

export async function updateLanguage(id: string, body: LanguageUpdate): Promise<Language> {
  const { data } = await apiClient.patch<Language>(`/admin/languages/${id}`, body);
  return data;
}

export async function deleteLanguage(id: string): Promise<void> {
  await apiClient.delete(`/admin/languages/${id}`);
}