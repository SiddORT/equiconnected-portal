/**
 * Edit Provider page — /admin/providers/:id/edit
 * Fetches the provider and reuses ProviderForm with initialData.
 */
import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { extractErrorMessage } from '@/api/client';
import { getProvider } from '@/api/providers';
import { ErrorState } from '@/components/ui/ErrorState';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { PageHeader } from '@/components/layout/PageHeader';
import { ProviderForm } from '@/components/admin/ProviderForm';
import type { LoadingState, Provider } from '@/types';
import styles from './ProviderFormPage.module.css';

export function ProviderEditPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [provider, setProvider] = useState<Provider | null>(null);
  const [loadState, setLoadState] = useState<LoadingState>('loading');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!id) return;
    setLoadState('loading');
    try {
      setProvider(await getProvider(id));
      setLoadState('success');
    } catch (err) {
      setErrorMessage(extractErrorMessage(err, 'Failed to load provider.'));
      setLoadState('error');
    }
  }, [id]);

  useEffect(() => { void load(); }, [load]);

  return (
    <div className={styles.shell}>
      <PageHeader
        title={provider ? `Edit ${provider.name}` : 'Edit Provider'}
        subtitle="Update provider details."
        breadcrumbs={[
          { label: 'Admin' },
          { label: 'Providers', href: '/admin/providers' },
          { label: provider?.name ?? '…', href: id ? `/admin/providers/${id}` : undefined },
          { label: 'Edit' },
        ]}
      />
      <div className={styles.body}>
        {loadState === 'loading' && (
          <div className={styles.centered}>
            <LoadingSpinner size="lg" label="Loading provider…" />
          </div>
        )}
        {loadState === 'error' && (
          <ErrorState title="Failed to load provider" message={errorMessage ?? undefined} onRetry={load} />
        )}
        {loadState === 'success' && provider && (
          <ProviderForm
            initialData={provider}
            onSuccess={(saved) => navigate(`/admin/providers/${saved.id}`)}
            onCancel={() => navigate(`/admin/providers/${provider.id}`)}
          />
        )}
      </div>
    </div>
  );
}
