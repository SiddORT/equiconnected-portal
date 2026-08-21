import { apiClient } from './client';

/** Record one aggregate public landing-page visit. No visitor details are sent. */
export async function recordPublicVisit(): Promise<void> {
  await apiClient.post('/public/visits');
}