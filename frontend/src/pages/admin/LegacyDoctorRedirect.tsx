/**
 * Legacy /admin/doctors/:id(/edit) routes — doctors are now managed as
 * providers, so redirect to the equivalent Provider Management page.
 */
import { Navigate, useParams } from 'react-router-dom';

export function LegacyDoctorRedirect({ edit = false }: { edit?: boolean }) {
  const { id } = useParams<{ id: string }>();
  if (!id) return <Navigate to="/admin/providers" replace />;
  return <Navigate to={`/admin/providers/${id}${edit ? '/edit' : ''}`} replace />;
}
