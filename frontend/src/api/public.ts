import { apiClient } from './client';
import type {
  MessageResponse,
  ProviderType,
  PublicProviderDiscovery,
  SubscriberRegistrationRequest,
} from '@/types';

export interface ContactMessageRequest {
  name: string;
  email: string;
  enquiry_type: 'general' | 'listing' | 'partnership' | 'other';
  phone?: string;
  message: string;
}

export async function sendContactMessage(request: ContactMessageRequest): Promise<MessageResponse> {
  const { data } = await apiClient.post<MessageResponse>('/public/contact', request);
  return data;
}

/** Record one aggregate public landing-page visit. No visitor details are sent. */
export async function recordPublicVisit(): Promise<void> {
  await apiClient.post('/public/visits');
}

export async function registerSubscriber(
  request: SubscriberRegistrationRequest
): Promise<MessageResponse> {
  const { data } = await apiClient.post<MessageResponse>('/public/subscribers', request);
  return data;
}

export async function listPublicProviders(params?: {
  provider_type?: ProviderType;
  latitude?: number;
  longitude?: number;
  limit?: number;
}): Promise<PublicProviderDiscovery[]> {
  const { data } = await apiClient.get<PublicProviderDiscovery[]>('/public/providers', { params });
  return data;
}