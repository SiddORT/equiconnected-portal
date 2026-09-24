import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '@/app/AuthContext';
import { LoadingScreen } from '@/components/ui/LoadingScreen';
import { hasMemberRole } from '@/features/member/memberAccess';

export function ProviderAuthGuard() {
  const { isAuthenticated, isLoading, user } = useAuth();
  const location = useLocation();

  if (isLoading) return <LoadingScreen message="Verifying session…" />;
  if (!isAuthenticated) {
    return <Navigate to="/provider/login" state={{ from: location }} replace />;
  }
  const roles = user?.roles?.length ? user.roles : [user?.role ?? ''];
  if (!roles.includes('provider')) {
    return <Navigate to={hasMemberRole(user) ? '/' : roles.includes('admin') ? '/admin/dashboard' : '/'} replace />;
  }
  return <Outlet />;
}