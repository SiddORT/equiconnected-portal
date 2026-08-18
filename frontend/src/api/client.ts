/**
 * Axios client with:
 *  - Authorization header injection (access token from AuthContext)
 *  - Automatic token refresh on 401
 *  - Consistent error handling
 *
 * Access token is stored in memory only (never localStorage).
 * Refresh token is in an httpOnly cookie — never touched by JS.
 */
import axios, {
  AxiosError,
  AxiosInstance,
  InternalAxiosRequestConfig,
} from 'axios';

// Store the access token in module scope (in-memory only, not localStorage)
let accessToken: string | null = null;
let refreshPromise: Promise<string | null> | null = null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function getAccessToken(): string | null {
  return accessToken;
}

// ── Axios instance ─────────────────────────────────────────────────────────

export const apiClient: AxiosInstance = axios.create({
  baseURL: '/api/v1',
  withCredentials: true, // send httpOnly refresh-token cookie
  headers: {
    'Content-Type': 'application/json',
  },
});

// ── Request interceptor — attach access token ──────────────────────────────

apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    if (accessToken && config.headers) {
      config.headers['Authorization'] = `Bearer ${accessToken}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// ── Response interceptor — auto-refresh on 401 ────────────────────────────

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as InternalAxiosRequestConfig & {
      _retry?: boolean;
    };

    // Only attempt refresh on 401 from non-auth endpoints and only once
    if (
      error.response?.status === 401 &&
      !original._retry &&
      original.url !== '/auth/refresh' &&
      original.url !== '/auth/login'
    ) {
      original._retry = true;

      // Deduplicate concurrent refresh requests
      if (!refreshPromise) {
        refreshPromise = apiClient
          .post<{ access_token: string }>('/auth/refresh')
          .then((res) => {
            setAccessToken(res.data.access_token);
            return res.data.access_token;
          })
          .catch(() => {
            setAccessToken(null);
            return null;
          })
          .finally(() => {
            refreshPromise = null;
          });
      }

      const newToken = await refreshPromise;
      if (newToken && original.headers) {
        original.headers['Authorization'] = `Bearer ${newToken}`;
        return apiClient(original);
      }
    }

    return Promise.reject(error);
  }
);

/**
 * Extract a user-friendly error message from an Axios error.
 * Never exposes raw backend stack traces.
 */
export function extractErrorMessage(error: unknown, fallback = 'An unexpected error occurred.'): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data;
    if (data?.error?.message) return data.error.message;
    if (data?.detail?.message) return data.detail.message;
    if (typeof data?.detail === 'string') return data.detail;
    if (error.response?.status === 401) return 'Authentication required. Please log in.';
    if (error.response?.status === 403) return 'You do not have permission to perform this action.';
    if (error.response?.status === 404) return 'The requested resource was not found.';
    if (error.response?.status >= 500) return 'A server error occurred. Please try again later.';
  }
  return fallback;
}
