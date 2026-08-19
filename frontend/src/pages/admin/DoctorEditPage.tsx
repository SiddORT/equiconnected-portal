/**
 * Edit Doctor page — /admin/doctors/:id/edit
 * Fetches the doctor and reuses DoctorForm with initialData.
 */
import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { extractErrorMessage } from '@/api/client';
import { getDoctor } from '@/api/doctors';
import { ErrorState } from '@/components/ui/ErrorState';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { PageHeader } from '@/components/layout/PageHeader';
import { DoctorForm } from '@/components/admin/DoctorForm';
import type { DoctorResponse, LoadingState } from '@/types';
import styles from './ProviderFormPage.module.css';

export function DoctorEditPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [doctor, setDoctor] = useState<DoctorResponse | null>(null);
  const [loadState, setLoadState] = useState<LoadingState>('loading');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!id) return;
    setLoadState('loading');
    try {
      setDoctor(await getDoctor(id));
      setLoadState('success');
    } catch (err) {
      setErrorMessage(extractErrorMessage(err, 'Failed to load doctor.'));
      setLoadState('error');
    }
  }, [id]);

  useEffect(() => { void load(); }, [load]);

  return (
    <div className={styles.shell}>
      <PageHeader
        title={doctor ? `Edit ${doctor.name}` : 'Edit Doctor'}
        subtitle="Update doctor details."
        breadcrumbs={[
          { label: 'Admin' },
          { label: 'Doctors', href: '/admin/doctors' },
          { label: doctor?.name ?? '…', href: id ? `/admin/doctors/${id}` : undefined },
          { label: 'Edit' },
        ]}
      />
      <div className={styles.body}>
        {loadState === 'loading' && (
          <div className={styles.centered}>
            <LoadingSpinner size="lg" label="Loading doctor…" />
          </div>
        )}
        {loadState === 'error' && (
          <ErrorState title="Failed to load doctor" message={errorMessage ?? undefined} onRetry={load} />
        )}
        {loadState === 'success' && doctor && (
          <DoctorForm
            initialData={doctor}
            onSuccess={(saved) => navigate(`/admin/doctors/${saved.id}`)}
            onCancel={() => navigate(`/admin/doctors/${doctor.id}`)}
          />
        )}
      </div>
    </div>
  );
}
