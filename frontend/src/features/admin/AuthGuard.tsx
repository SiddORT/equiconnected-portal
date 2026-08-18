/**
 * AuthGuard — wraps routes that require authentication.
 * Redirects unauthenticated users to /admin/login.
 * Shows a loading state while the session is being restored.
 */
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '@/app/AuthContext';
import { LoadingScreen } from '@/components/ui/LoadingScreen';

interface AuthGuardProps {
  requiredRole?: string;
}

export function AuthGuard({ requiredRole }: AuthGuardProps) {
  const { isAuthenticated, isLoading, user } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return <LoadingScreen message="Verifying session…" />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/admin/login" state={{ from: location }} replace />;
  }

  if (requiredRole && user?.role !== requiredRole) {
    return <Navigate to="/admin/login" replace />;
  }

  return <Outlet />;
}
