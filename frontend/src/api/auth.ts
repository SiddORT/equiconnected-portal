/**
 * Auth API endpoint functions.
 */
import { apiClient } from './client';
import type {
  LoginRequest,
  LoginResponse,
  EmailVerificationResponse,
  MessageResponse,
  RegistrationRequest,
  UserProfile,
} from '@/types';

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

export async function register(payload: RegistrationRequest): Promise<MessageResponse> {
  const { data } = await apiClient.post<MessageResponse>('/auth/register', payload);
  return data;
}

export async function verifyEmail(token: string): Promise<EmailVerificationResponse> {
  const { data } = await apiClient.post<EmailVerificationResponse>('/auth/verify-email', { token });
  return data;
}
