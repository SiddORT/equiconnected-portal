import { getAccessToken } from '@/api/client';

export type MemberContactAction = 'phone' | 'email' | 'website';

const MAX_ATTEMPTS = 2;
const RETRY_DELAY_MS = 150;

function createEventKey(): string | null {
  if (typeof crypto === 'undefined' || typeof crypto.getRandomValues !== 'function') return null;

  const timestamp = Date.now();
  if (!Number.isSafeInteger(timestamp) || timestamp < 0 || timestamp > 0xffffffffffff) return null;

  const bytes = new Uint8Array(16);
  try {
    crypto.getRandomValues(bytes);
  } catch {
    return null;
  }

  let remainingTimestamp = timestamp;
  for (let index = 5; index >= 0; index -= 1) {
    bytes[index] = remainingTimestamp & 0xff;
    remainingTimestamp = Math.floor(remainingTimestamp / 256);
  }
  bytes[6] = (bytes[6] & 0x0f) | 0x70;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;

  const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('');
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

function isRetryableStatus(status: number): boolean {
  return status === 408 || status === 425 || status === 429 || status >= 500;
}

function waitForRetry(): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, RETRY_DELAY_MS));
}

async function sendContactClick(
  endpoint: string,
  action: MemberContactAction,
  eventKey: string,
  accessToken: string,
): Promise<void> {
  for (let attempt = 0; attempt < MAX_ATTEMPTS; attempt += 1) {
    try {
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ action, event_key: eventKey }),
        keepalive: true,
        credentials: 'omit',
      });
      if (response.ok || !isRetryableStatus(response.status) || attempt === MAX_ATTEMPTS - 1) {
        return;
      }
    } catch {
      if (attempt === MAX_ATTEMPTS - 1) return;
    }

    await waitForRetry();
  }
}

/**
 * Records a best-effort member contact activation without participating in the
 * native link action. The event key exists only for this activation and its
 * bounded retry; no member identity or contact destination is sent.
 */
export function recordMemberContactClick(
  providerId: string,
  action: MemberContactAction,
): void {
  try {
    if (!providerId) return;

    const eventKey = createEventKey();
    if (!eventKey) return;
    const accessToken = getAccessToken();
    if (!accessToken) return;

    const endpoint = `/api/v1/member/providers/${encodeURIComponent(providerId)}/contact-click`;
    void sendContactClick(endpoint, action, eventKey, accessToken).catch(() => undefined);
  } catch {
    // Measurement is optional; never let it interfere with the native contact link.
  }
}