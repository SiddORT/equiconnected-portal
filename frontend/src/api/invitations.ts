/**
 * Typed client functions for provider invitations.
 * - Admin side uses the authenticated apiClient.
 * - Public (token-based) side uses a dedicated axios instance WITHOUT the
 *   admin auth header or refresh-cookie credentials — those endpoints are
 *   authenticated solely by the invitation token in the URL.
 */
import { apiClient } from './client';
import axios, { AxiosInstance } from 'axios';
import type {
  Invitation,
  InvitationCreate,
  InvitationDraftPayload,
  InvitationListParams,
  InvitationSpecialization,
  InvitationTokenData,
  OrgRequestCreatePayload,
  OrgRequestResult,
  OrgSearchResult,
  OrgSuggestion,
  PaginatedResponse,
} from '@/types';

export async function listInvitations(
  params?: InvitationListParams
): Promise<PaginatedResponse<Invitation>> {
  const { data } = await apiClient.get<PaginatedResponse<Invitation>>('/admin/invitations', { params });
  return data;
}

export async function createInvitation(body: InvitationCreate): Promise<Invitation> {
  const { data } = await apiClient.post<Invitation>('/admin/invitations', body);
  return data;
}

export async function resendInvitation(id: string): Promise<Invitation> {
  const { data } = await apiClient.post<Invitation>(`/admin/invitations/${id}/resend`);
  return data;
}

export async function cancelInvitation(id: string): Promise<Invitation> {
  const { data } = await apiClient.post<Invitation>(`/admin/invitations/${id}/cancel`);
  return data;
}

export async function sendPortalAccess(id: string): Promise<Invitation> {
  const { data } = await apiClient.post<Invitation>(`/admin/invitations/${id}/portal-access`);
  return data;
}

const publicClient: AxiosInstance = axios.create({
  baseURL: '/api/v1',
  withCredentials: false,
  headers: { 'Content-Type': 'application/json' },
});

export async function requestNewOrganization(
  token: string,
  body: OrgRequestCreatePayload
): Promise<OrgRequestResult> {
  const { data } = await publicClient.post<OrgRequestResult>(
    `/provider/invitations/${encodeURIComponent(token)}/organization-requests`,
    body
  );
  return data;
}

export function getPublicErrorStatus(error: unknown): number | null {
  return axios.isAxiosError(error) ? error.response?.status ?? null : null;
}

/**
 * Map a FastAPI 422 validation response to `{ fieldName: message }`.
 * Handles both pydantic loc-array errors and the custom
 * `{code: "provider_validation_failed", message}` shape (returned as `_form`).
 */
export function extractSubmitFieldErrors(error: unknown): Record<string, string> {
  const out: Record<string, string> = {};
  if (!axios.isAxiosError(error) || error.response?.status !== 422) return out;
  const detail = error.response.data?.detail;
  if (Array.isArray(detail)) {
    for (const item of detail) {
      const loc: unknown[] = Array.isArray(item?.loc) ? item.loc : [];
      const field = loc.filter((part) => part !== 'body').map(String).join('.');
      if (field && typeof item?.msg === 'string' && !out[field]) out[field] = item.msg;
    }
  } else if (detail && typeof detail === 'object' && typeof detail.message === 'string') {
    out._form = detail.message;
  } else if (typeof detail === 'string') {
    out._form = detail;
  }
  return out;
}

export async function submitInvitation(
  token: string,
  body: InvitationDraftPayload
): Promise<InvitationTokenData> {
  const { data } = await publicClient.post<InvitationTokenData>(
    `/provider/invitations/${encodeURIComponent(token)}/submit`,
    body
  );
  return data;
}

/** Backend error code from a structured `detail: {code, message}` response. */
export function getPublicErrorCode(error: unknown): string | null {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
      return typeof detail.code === 'string' ? detail.code : null;
    }
  }
  return null;
}

export async function getInvitationSpecializations(
  token: string
): Promise<InvitationSpecialization[]> {
  const { data } = await publicClient.get<{ data: InvitationSpecialization[] }>(
    `/provider/invitations/${encodeURIComponent(token)}/specializations`
  );
  return data.data;
}

export async function searchOrganizations(
  q: string,
  type?: 'HOSPITAL' | 'CLINIC',
  page = 1
): Promise<PaginatedResponse<OrgSearchResult>> {
  const { data } = await publicClient.get<PaginatedResponse<OrgSearchResult>>(
    '/provider/organizations/search',
    { params: { q: q || undefined, type: type || undefined, page } }
  );
  return data;
}

export async function associateOrganization(
  token: string,
  organizationId: string
): Promise<{ id: string; status: string }> {
  const { data } = await publicClient.post<{ id: string; status: string }>(
    `/provider/invitations/${encodeURIComponent(token)}/organizations`,
    { organization_id: organizationId }
  );
  return data;
}

export async function getInvitationByToken(token: string): Promise<InvitationTokenData> {
  const { data } = await publicClient.get<InvitationTokenData>(
    `/provider/invitations/${encodeURIComponent(token)}`
  );
  return data;
}

export async function saveInvitationDraft(
  token: string,
  body: InvitationDraftPayload
): Promise<InvitationTokenData> {
  const { data } = await publicClient.post<InvitationTokenData>(
    `/provider/invitations/${encodeURIComponent(token)}/save`,
    body
  );
  return data;
}

/** "Did you mean?" suggestions from a 409 organization-request response. */
export function getOrgSuggestions(error: unknown): OrgSuggestion[] | null {
  if (axios.isAxiosError(error) && error.response?.status === 409) {
    const detail = error.response.data?.detail;
    if (detail?.code === 'organization_suggestions' && Array.isArray(detail.suggestions)) {
      return detail.suggestions as OrgSuggestion[];
    }
  }
  return null;
}
