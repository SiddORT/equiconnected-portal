import { useLocation } from 'react-router-dom';
import { getDashboardVisits } from '@/api/admin';
import { getMemberVisitCalendar } from '@/api/providers';
import { VisitingProviderCalendar } from '@/components/dashboard/VisitingProviderCalendar';
import styles from './VisitingProviderCalendarPage.module.css';

function VisitingProviderCalendarPage({ audience }: { audience: 'admin' | 'member' }) {
  const location = useLocation();
  const isAdmin = audience === 'admin';
  const returnPath = `${isAdmin ? '/admin/dashboard' : '/providers'}${location.search}`;
  const providerPath = isAdmin
    ? (id: string) => `/admin/providers/${id}`
    : (id: string) => `/providers/${id}${location.search}`;

  return (
    <main className={styles.page}>
      <div className={styles.paperTexture} aria-hidden="true" />
      <VisitingProviderCalendar
        fullPage
        audience={audience}
        loadMonth={isAdmin ? getDashboardVisits : getMemberVisitCalendar}
        providerHref={providerPath}
        providerState={location.state}
        returnHref={returnPath}
        returnState={location.state}
      />
    </main>
  );
}

export function AdminVisitingProviderCalendarPage() {
  return <VisitingProviderCalendarPage audience="admin" />;
}

export function MemberVisitingProviderCalendarPage() {
  return <VisitingProviderCalendarPage audience="member" />;
}