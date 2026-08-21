/**
 * Provider API client functions — mirror backend /admin/providers endpoints.
 */
import { apiClient } from './client';
import type {
  PaginatedResponse,
  Provider,
  ProviderCreate,
  ProviderListItem,
  ProviderEmail,
  ProviderEmailCreate,
  ProviderListParams,
  ProviderLocation,
  ProviderPhone,
  ProviderPhoneCreate,
  ProviderLocationCreate,
  ProviderLocationUpdate,
  ProviderPhoto,
  ProviderPhotoCreate,
  ProviderPhotoUpdate,
  ProviderStatus,
  ProviderUpdate,
  PublicationStatus,
  MemberProviderDetail,
  MemberProviderListItem,
  MemberProviderListParams,
  MemberProviderReview,
  ProviderPortalProfile,
  ProviderPortalUpdate,
  ProviderSpecializationBrief,
} from '@/types';

export async function getProviderPortalProfile(): Promise<ProviderPortalProfile> {
  const { data } = await apiClient.get<ProviderPortalProfile>('/provider/portal/profile');
  return data;
}

export async function updateProviderPortalProfile(
  body: ProviderPortalUpdate
): Promise<ProviderPortalProfile> {
  const { data } = await apiClient.patch<ProviderPortalProfile>('/provider/portal/profile', body);
  return data;
}

export async function discardProviderPortalProfileUpdate(): Promise<ProviderPortalProfile> {
  const { data } = await apiClient.post<ProviderPortalProfile>('/provider/portal/profile-update/discard');
  return data;
}

export async function getProviderPortalSpecializations(): Promise<ProviderSpecializationBrief[]> {
  const { data } = await apiClient.get<ProviderSpecializationBrief[]>('/provider/portal/specializations');
  return data;
}

// ── Member directory ────────────────────────────────────────────────────────

export async function listMemberProviders(
  params?: MemberProviderListParams
): Promise<PaginatedResponse<MemberProviderListItem>> {
  const { data } = await apiClient.get<PaginatedResponse<MemberProviderListItem>>(
    '/member/providers',
    { params }
  );
  return data;
}

export async function getMemberProvider(id: string): Promise<MemberProviderDetail> {
  const { data } = await apiClient.get<MemberProviderDetail>(`/member/providers/${id}`);
  return data;
}

export async function saveMemberProviderReview(
  id: string,
  body: { rating: number; comment: string }
): Promise<MemberProviderReview> {
  const { data } = await apiClient.put<MemberProviderReview>(
    `/member/providers/${id}/review`,
    body
  );
  return data;
}

export async function listProviders(
  params?: ProviderListParams
): Promise<PaginatedResponse<ProviderListItem>> {
  const { data } = await apiClient.get<PaginatedResponse<ProviderListItem>>('/admin/providers', {
    params,
  });
  return data;
}

export async function getProvider(id: string): Promise<Provider> {
  const { data } = await apiClient.get<Provider>(`/admin/providers/${id}`);
  return data;
}

export async function createProvider(body: ProviderCreate): Promise<Provider> {
  const { data } = await apiClient.post<Provider>('/admin/providers', body);
  return data;
}

export async function updateProvider(id: string, body: ProviderUpdate): Promise<Provider> {
  const { data } = await apiClient.patch<Provider>(`/admin/providers/${id}`, body);
  return data;
}

export async function updateProviderStatus(id: string, status: ProviderStatus): Promise<Provider> {
  const { data } = await apiClient.patch<Provider>(`/admin/providers/${id}/status`, { status });
  return data;
}

export async function updateProviderPublication(
  id: string,
  publication_status: PublicationStatus
): Promise<Provider> {
  const { data } = await apiClient.patch<Provider>(`/admin/providers/${id}/publication`, {
    publication_status,
  });
  return data;
}

// ── Specializations sub-resource ──────────────────────────────────────────────

export async function addProviderSpecialization(
  id: string,
  specializationId: string
): Promise<Provider> {
  const { data } = await apiClient.post<Provider>(`/admin/providers/${id}/specializations`, {
    specialization_id: specializationId,
  });
  return data;
}

export async function removeProviderSpecialization(
  id: string,
  specId: string
): Promise<Provider> {
  const { data } = await apiClient.delete<Provider>(
    `/admin/providers/${id}/specializations/${specId}`
  );
  return data;
}

// ── Locations sub-resource ────────────────────────────────────────────────────

export async function createProviderLocation(
  id: string,
  body: ProviderLocationCreate
): Promise<ProviderLocation> {
  const { data } = await apiClient.post<ProviderLocation>(`/admin/providers/${id}/locations`, body);
  return data;
}

export async function updateProviderLocation(
  id: string,
  locId: string,
  body: ProviderLocationUpdate
): Promise<ProviderLocation> {
  const { data } = await apiClient.patch<ProviderLocation>(
    `/admin/providers/${id}/locations/${locId}`,
    body
  );
  return data;
}

export async function deleteProviderLocation(id: string, locId: string): Promise<void> {
  await apiClient.delete(`/admin/providers/${id}/locations/${locId}`);
}

// ── Phones sub-resource ───────────────────────────────────────────────────────

export async function addProviderPhone(
  id: string,
  body: ProviderPhoneCreate
): Promise<ProviderPhone> {
  const { data } = await apiClient.post<ProviderPhone>(`/admin/providers/${id}/phones`, body);
  return data;
}

export async function removeProviderPhone(id: string, phoneId: string): Promise<void> {
  await apiClient.delete(`/admin/providers/${id}/phones/${phoneId}`);
}

// ── Emails sub-resource ───────────────────────────────────────────────────────

export async function addProviderEmail(
  id: string,
  body: ProviderEmailCreate
): Promise<ProviderEmail> {
  const { data } = await apiClient.post<ProviderEmail>(`/admin/providers/${id}/emails`, body);
  return data;
}

export async function removeProviderEmail(id: string, emailId: string): Promise<void> {
  await apiClient.delete(`/admin/providers/${id}/emails/${emailId}`);
}

// ── Photos sub-resource ───────────────────────────────────────────────────────

export async function uploadProviderPhoto(
  id: string,
  file: File,
  meta?: { alt_text?: string | null; caption?: string | null; display_order?: number; is_thumbnail?: boolean }
): Promise<ProviderPhoto> {
  const form = new FormData();
  form.append('file', file);
  if (meta?.alt_text) form.append('alt_text', meta.alt_text);
  if (meta?.caption) form.append('caption', meta.caption);
  if (meta?.display_order !== undefined) form.append('display_order', String(meta.display_order));
  if (meta?.is_thumbnail !== undefined) form.append('is_thumbnail', String(meta.is_thumbnail));

  const { data } = await apiClient.post<ProviderPhoto>(`/admin/providers/${id}/photos`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

/** @deprecated Use uploadProviderPhoto instead */
export async function createProviderPhoto(
  id: string,
  body: ProviderPhotoCreate
): Promise<ProviderPhoto> {
  const { data } = await apiClient.post<ProviderPhoto>(`/admin/providers/${id}/photos`, body);
  return data;
}

export async function updateProviderPhoto(
  id: string,
  photoId: string,
  body: ProviderPhotoUpdate
): Promise<ProviderPhoto> {
  const { data } = await apiClient.patch<ProviderPhoto>(
    `/admin/providers/${id}/photos/${photoId}`,
    body
  );
  return data;
}

export async function deleteProviderPhoto(id: string, photoId: string): Promise<void> {
  await apiClient.delete(`/admin/providers/${id}/photos/${photoId}`);
}

export async function setProviderThumbnail(id: string, photoId: string): Promise<ProviderPhoto> {
  const { data } = await apiClient.patch<ProviderPhoto>(
    `/admin/providers/${id}/photos/${photoId}/thumbnail`
  );
  return data;
}
