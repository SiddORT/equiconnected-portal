/**
 * Create Doctor page — /admin/doctors/new
 */
import { useNavigate } from 'react-router-dom';
import { PageHeader } from '@/components/layout/PageHeader';
import { DoctorForm } from '@/components/admin/DoctorForm';
import styles from './ProviderFormPage.module.css';

export function DoctorNewPage() {
  const navigate = useNavigate();

  return (
    <div className={styles.shell}>
      <PageHeader
        title="Add Doctor"
        subtitle="Create a new doctor profile."
        breadcrumbs={[
          { label: 'Admin' },
          { label: 'Doctors', href: '/admin/doctors' },
          { label: 'New' },
        ]}
      />
      <div className={styles.body}>
        <DoctorForm
          onSuccess={(doctor) => navigate(`/admin/doctors/${doctor.id}`)}
          onCancel={() => navigate('/admin/doctors')}
        />
      </div>
    </div>
  );
}
