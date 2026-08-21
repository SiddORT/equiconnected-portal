import { apiClient } from './client';
import type { MessageResponse, SubscriberRegistrationRequest } from '@/types';

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