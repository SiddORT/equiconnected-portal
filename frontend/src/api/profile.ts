import { apiClient } from './client';
import type {
  Horse, HorsePayload, MemberProfile, PersonalProfileUpdate, PostalLookupResult,
  StableProfile, StableProfileUpdate,
} from '@/types';

export async function getProfile(): Promise<MemberProfile> {
  const { data } = await apiClient.get<MemberProfile>('/profile');
  return data;
}

export async function savePersonal(payload: PersonalProfileUpdate): Promise<MemberProfile> {
  const { data } = await apiClient.put<MemberProfile>('/profile/personal', payload);
  return data;
}

export async function saveStable(payload: StableProfileUpdate): Promise<StableProfile> {
  const { data } = await apiClient.put<StableProfile>('/profile/stable', payload);
  return data;
}

export async function createHorse(payload: HorsePayload): Promise<Horse> {
  const { data } = await apiClient.post<Horse>('/profile/horses', payload);
  return data;
}

export async function saveHorse(id: string, payload: HorsePayload): Promise<Horse> {
  const { data } = await apiClient.put<Horse>(`/profile/horses/${id}`, payload);
  return data;
}

export async function deleteHorse(id: string): Promise<void> {
  await apiClient.delete(`/profile/horses/${id}`);
}

export async function uploadHorsePhoto(id: string, file: File): Promise<Horse> {
  const form = new FormData();
  form.append('file', file);
  const { data } = await apiClient.post<Horse>(`/profile/horses/${id}/photo`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

export async function removeHorsePhoto(id: string): Promise<void> {
  await apiClient.delete(`/profile/horses/${id}/photo`);
}

export async function lookupPostalCode(country: string, postalCode: string): Promise<PostalLookupResult> {
  const { data } = await apiClient.get<PostalLookupResult>('/profile/postal-lookup', {
    params: { country, postal_code: postalCode },
  });
  return data;
}