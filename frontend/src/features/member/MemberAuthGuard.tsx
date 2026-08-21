import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '@/app/AuthContext';
import { LoadingScreen } from '@/components/ui/LoadingScreen';

const MEMBER_ROLES = new Set(['horse_owner', 'stable_manager']);

export function MemberAuthGuard() {
  const { isAuthenticated, isLoading, user } = useAuth();
  const location = useLocation();

  if (isLoading) return <LoadingScreen message="Verifying session…" />;
  if (!isAuthenticated) return <Navigate to="/login" state={{ from: location }} replace />;

  const roles = user?.roles?.length ? user.roles : [user?.role ?? ''];
  if (!roles.some((role) => MEMBER_ROLES.has(role))) {
    return <Navigate to="/admin/login" replace />;
  }
  return <Outlet />;
}