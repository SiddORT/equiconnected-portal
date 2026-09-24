/**
 * Auth API endpoint functions.
 */
import { apiClient } from './client';
import type {
  LoginRequest,
  LoginResponse,
  EmailVerificationResponse,
  MessageResponse,
  ProviderRegistrationRequest,
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

export interface RegistrationResponse extends MessageResponse {
  email_sent: boolean;
}

export async function resendVerification(email: string): Promise<MessageResponse> {
  const { data } = await apiClient.post<MessageResponse>('/auth/resend-verification', { email });
  return data;
}

export async function register(payload: RegistrationRequest): Promise<RegistrationResponse> {
  const { data } = await apiClient.post<RegistrationResponse>('/auth/register', payload);
  return data;
}

export async function registerProvider(
  payload: ProviderRegistrationRequest
): Promise<RegistrationResponse> {
  const { data } = await apiClient.post<RegistrationResponse>('/auth/provider-register', payload);
  return data;
}

export async function listProviderSignupSpecializations(): Promise<Array<{ id: string; name: string }>> {
  const { data } = await apiClient.get<Array<{ id: string; name: string }>>('/auth/provider-specializations');
  return data;
}

export async function listProviderSignupLanguages(): Promise<Array<{ id: string; name: string; code: string }>> {
  const { data } = await apiClient.get<Array<{ id: string; name: string; code: string }>>('/auth/provider-languages');
  return data;
}

export interface PostalCandidate {
  country: string;
  country_code?: string;
  state_province: string;
  city: string;
  postal_code: string;
  display_name: string;
}

export async function lookupProviderPostalCode(postalCode: string, signal?: AbortSignal): Promise<{
  status: 'match' | 'no_match' | 'unavailable';
  candidates: PostalCandidate[];
}> {
  const { data } = await apiClient.get('/auth/provider-postal-lookup', {
    params: { postal_code: postalCode }, signal,
  });
  return data;
}

export async function verifyEmail(token: string): Promise<EmailVerificationResponse> {
  const { data } = await apiClient.post<EmailVerificationResponse>('/auth/verify-email', { token });
  return data;
}

export async function setupProviderPortalPassword(
  token: string,
  password: string,
  password_confirmation: string
): Promise<MessageResponse> {
  const { data } = await apiClient.post<MessageResponse>('/auth/provider-portal/setup-password', {
    token,
    password,
    password_confirmation,
  });
  return data;
}
