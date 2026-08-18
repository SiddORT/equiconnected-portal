/**
 * Authentication context — centralized auth state for the entire app.
 * Access token is in memory; refresh token is in an httpOnly cookie.
 */
import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from 'react';

import * as authApi from '@/api/auth';
import { setAccessToken } from '@/api/client';
import type { UserProfile } from '@/types';

interface AuthState {
  user: UserProfile | null;
  isAuthenticated: boolean;
  isLoading: boolean;
}

interface AuthContextValue extends AuthState {
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null,
    isAuthenticated: false,
    isLoading: true, // true until we've tried to restore the session
  });

  // ── Restore session on mount ───────────────────────────────────────────
  useEffect(() => {
    let cancelled = false;
    authApi
      .refreshToken()
      .then((res) => {
        if (!cancelled) {
          setAccessToken(res.access_token);
          setState({ user: res.user, isAuthenticated: true, isLoading: false });
        }
      })
      .catch(() => {
        if (!cancelled) {
          setAccessToken(null);
          setState({ user: null, isAuthenticated: false, isLoading: false });
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // ── Login ──────────────────────────────────────────────────────────────
  const login = useCallback(async (email: string, password: string) => {
    const res = await authApi.login({ email, password });
    setAccessToken(res.access_token);
    setState({ user: res.user, isAuthenticated: true, isLoading: false });
  }, []);

  // ── Logout ─────────────────────────────────────────────────────────────
  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } finally {
      setAccessToken(null);
      setState({ user: null, isAuthenticated: false, isLoading: false });
    }
  }, []);

  return (
    <AuthContext.Provider value={{ ...state, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within <AuthProvider>');
  return ctx;
}
