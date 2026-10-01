import axios from 'axios';
import { useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';
import { apiClient } from '@/api/client';

export type PublicTrafficCategory =
  | 'home'
  | 'animation'
  | 'signup'
  | 'provider_signup'
  | 'terms'
  | 'privacy';

export type MemberTrafficCategory = 'provider_directory' | 'provider_profile';
export type TrafficRouteLocation = {
  key: string;
  pathname: string;
  search: string;
  hash: string;
  category: PublicTrafficCategory | MemberTrafficCategory;
};

type TrafficPayload = {
  category: PublicTrafficCategory | MemberTrafficCategory;
  navigation_key: string;
  first_eligible_view_today: boolean;
  provider_id?: string;
};

const publicTrafficClient = axios.create({
  baseURL: '/api/v1',
  withCredentials: false,
  headers: { 'Content-Type': 'application/json' },
  timeout: 2500,
});

const VISITOR_DAY_STORAGE_KEY = 'equiconnected-traffic-visitor-day';
const rememberedNavigationKeys = new Set<string>();
const MAX_REMEMBERED_NAVIGATION_KEYS = 256;
let cachedSystemTimezone: string | null = null;
let timezoneRequest: Promise<string | null> | null = null;

function uuid(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID();
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (character) => {
    const random = Math.floor(Math.random() * 16);
    return (character === 'x' ? random : (random & 0x3) | 0x8).toString(16);
  });
}

function readSystemTimezone(): Promise<string | null> {
  if (cachedSystemTimezone) return Promise.resolve(cachedSystemTimezone);
  if (!timezoneRequest) {
    timezoneRequest = publicTrafficClient
      .get<{ timezone?: string }>('/system-settings', { timeout: 2500 })
      .then(({ data }) => {
        if (typeof data.timezone !== 'string' || !data.timezone.trim()) return null;
        try {
          new Intl.DateTimeFormat('en-US', { timeZone: data.timezone }).format(new Date());
          cachedSystemTimezone = data.timezone;
          return cachedSystemTimezone;
        } catch {
          return null;
        }
      })
      .catch(() => null)
      .finally(() => {
        timezoneRequest = null;
      });
  }
  return timezoneRequest;
}

function claimFirstBrowserViewToday(timezone: string | null): boolean {
  if (!timezone) return false;
  try {
    const todayParts = new Intl.DateTimeFormat('en-US', {
      timeZone: timezone,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    }).formatToParts(new Date());
    const datePart = Object.fromEntries(
      todayParts
        .filter((part) => ['year', 'month', 'day'].includes(part.type))
        .map((part) => [part.type, part.value]),
    );
    const today = `${datePart.year}-${datePart.month}-${datePart.day}`;
    if (window.localStorage.getItem(VISITOR_DAY_STORAGE_KEY) === today) return false;
    window.localStorage.setItem(VISITOR_DAY_STORAGE_KEY, today);
    return true;
  } catch {
    // Without storage, prefer a lower-quality estimate to duplicate inflation.
    return false;
  }
}

export function hasSensitiveTrafficUrlParameter(search: string, hash: string): boolean {
  const sensitiveKey = /(token|secret|credential|password|authorization|auth|code|jwt)/i;
  const queryParams = new URLSearchParams(search);
  if ([...queryParams.keys()].some((key) => sensitiveKey.test(key))) return true;
  const fragment = hash.replace(/^#/, '');
  const fragmentQuery = new URLSearchParams(
    fragment.includes('?') ? fragment.slice(fragment.indexOf('?') + 1) : fragment,
  );
  return [...fragmentQuery.keys()].some((key) => sensitiveKey.test(key));
}

function rememberNavigationKey(key: string): boolean {
  if (rememberedNavigationKeys.has(key)) return false;
  rememberedNavigationKeys.add(key);
  if (rememberedNavigationKeys.size > MAX_REMEMBERED_NAVIGATION_KEYS) {
    const oldest = rememberedNavigationKeys.values().next().value;
    if (oldest) rememberedNavigationKeys.delete(oldest);
  }
  return true;
}

function shouldRetry(error: unknown): boolean {
  if (!axios.isAxiosError(error)) return true;
  const status = error.response?.status;
  return status === undefined || status >= 500;
}

async function bestEffortPost(
  endpoint: string,
  payload: TrafficPayload,
  authenticatedMember: boolean,
): Promise<void> {
  const send = () => authenticatedMember
    ? apiClient.post(endpoint, payload, { timeout: 2500 })
    : publicTrafficClient.post(endpoint, payload, { timeout: 2500 });
  try {
    await send();
  } catch (error) {
    if (!shouldRetry(error)) return;
    try {
      // Reuse the same short-lived key. The server receipt makes this retry
      // idempotent even if the original response was lost after its commit.
      await send();
    } catch {
      // Analytics must never delay or block application navigation.
    }
  }
}

function deliver(
  category: TrafficPayload['category'],
  endpoint: string,
  authenticatedMember: boolean,
  providerId?: string,
): void {
  const navigationKey = uuid();
  if (!rememberNavigationKey(navigationKey)) return;
  void readSystemTimezone().then((timezone) => bestEffortPost(
    endpoint,
    {
      category,
      navigation_key: navigationKey,
      first_eligible_view_today: claimFirstBrowserViewToday(timezone),
      ...(providerId ? { provider_id: providerId } : {}),
    },
    authenticatedMember,
  ));
}

export function recordPublicTrafficView(category: PublicTrafficCategory): void {
  deliver(
    category,
    '/public/traffic/page-view',
    false,
  );
}

export function recordMemberTrafficView(
  category: MemberTrafficCategory,
  providerId?: string,
): void {
  if ((category === 'provider_profile') !== Boolean(providerId)) return;
  deliver(
    category,
    '/member/providers/traffic-view',
    true,
    providerId,
  );
}

export function isNewTrafficNavigation(
  previous: TrafficRouteLocation | null,
  current: TrafficRouteLocation,
): boolean {
  if (!previous) return true;
  if (previous.category !== current.category || previous.pathname !== current.pathname) {
    return true;
  }
  const sameUrl = previous.search === current.search && previous.hash === current.hash;
  return sameUrl && previous.key !== current.key;
}

export function usePublicTrafficRoute(
  category: PublicTrafficCategory,
  expectedPath: string,
): void {
  const location = useLocation();
  const lastLocation = useRef<TrafficRouteLocation | null>(null);

  useEffect(() => {
    const current: TrafficRouteLocation = {
      key: location.key,
      pathname: location.pathname,
      search: location.search,
      hash: location.hash,
      category,
    };
    if (
      location.pathname === expectedPath
      && !['/reset-password', '/forgot-password'].includes(location.pathname)
      && !hasSensitiveTrafficUrlParameter(location.search, location.hash)
      && isNewTrafficNavigation(lastLocation.current, current)
    ) {
      recordPublicTrafficView(category);
    }
    lastLocation.current = current;
  }, [
    category,
    expectedPath,
    location.hash,
    location.key,
    location.pathname,
    location.search,
  ]);
}