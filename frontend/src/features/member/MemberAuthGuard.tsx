import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '@/app/AuthContext';
import { LoadingScreen } from '@/components/ui/LoadingScreen';
import { hasMemberRole } from './memberAccess';

export function MemberAuthGuard() {
  const { isAuthenticated, isLoading, user } = useAuth();
  const location = useLocation();

  if (isLoading) return <LoadingScreen message="Verifying session…" />;
  if (!isAuthenticated) return <Navigate to="/login" state={{ from: location }} replace />;

  if (!hasMemberRole(user)) {
    return <Navigate to="/admin/login" replace />;
  }
  return <Outlet />;
}