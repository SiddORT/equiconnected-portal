/** Typed client functions for admin provider invitations. */
import { apiClient } from './client';
import type { Invitation, InvitationCreate, InvitationListParams, PaginatedResponse } from '@/types';

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