import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '@/app/AuthContext';
import { LoadingScreen } from '@/components/ui/LoadingScreen';

export function ProviderAuthGuard() {
  const { isAuthenticated, isLoading, user } = useAuth();
  const location = useLocation();

  if (isLoading) return <LoadingScreen message="Verifying session…" />;
  if (!isAuthenticated) {
    return <Navigate to="/provider/login" state={{ from: location }} replace />;
  }
  const roles = user?.roles?.length ? user.roles : [user?.role ?? ''];
  if (!roles.includes('provider')) {
    const member = roles.some((role) => role === 'horse_owner' || role === 'stable_manager');
    return <Navigate to={member ? '/providers' : '/admin/dashboard'} replace />;
  }
  return <Outlet />;
}