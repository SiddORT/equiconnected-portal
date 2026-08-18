/**
 * Create Provider page — /admin/providers/new
 */
import { useNavigate } from 'react-router-dom';
import { PageHeader } from '@/components/layout/PageHeader';
import { ProviderForm } from '@/components/admin/ProviderForm';
import styles from './ProviderFormPage.module.css';

export function ProviderNewPage() {
  const navigate = useNavigate();

  return (
    <div className={styles.shell}>
      <PageHeader
        title="Add Provider"
        subtitle="Create a new hospital, clinic, or doctor profile."
        breadcrumbs={[
          { label: 'Admin' },
          { label: 'Providers', href: '/admin/providers' },
          { label: 'New' },
        ]}
      />
      <div className={styles.body}>
        <ProviderForm
          onSuccess={(provider) => navigate(`/admin/providers/${provider.id}`)}
          onCancel={() => navigate('/admin/providers')}
        />
      </div>
    </div>
  );
}
