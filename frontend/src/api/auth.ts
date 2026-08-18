/**
 * Auth API endpoint functions.
 */
import { apiClient } from './client';
import type { LoginRequest, LoginResponse, UserProfile } from '@/types';

export async function login(credentials: LoginRequest): Promise<LoginResponse> {
  const { data } = await apiClient.post<LoginResponse>('/auth/login', credentials);
  return data;
}

export async function refreshToken(): Promise<LoginResponse> {
  const { data } = await apiClient.post<LoginResponse>('/auth/refresh');
  return data;
}

export async function logout(): Promise<void> {
  await apiClient.post('/auth/logout');
}

export async function getMe(): Promise<UserProfile> {
  const { data } = await apiClient.get<UserProfile>('/auth/me');
  return data;
}
