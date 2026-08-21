/**
 * Admin dashboard — /admin/dashboard
 * Loads real stats from the backend API. No hard-coded data.
 */
import { useCallback, useEffect, useState } from 'react';
import { getDashboardStats } from '@/api/admin';
import { extractErrorMessage } from '@/api/client';
import { useAuth } from '@/app/AuthContext';
import { Badge } from '@/components/ui/Badge';
import { Card } from '@/components/ui/Card';
import { ErrorState } from '@/components/ui/ErrorState';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { PageHeader } from '@/components/layout/PageHeader';
import { DashboardMap } from '@/components/dashboard/DashboardMap';
import { InvitationStatusChart } from '@/components/dashboard/InvitationStatusChart';
import { VisitorVisitsChart } from '@/components/dashboard/VisitorVisitsChart';
import type { DashboardStats, LoadingState } from '@/types';
import styles from './DashboardPage.module.css';

export function DashboardPage() {
  const { user } = useAuth();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loadState, setLoadState] = useState<LoadingState>('loading');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const loadStats = useCallback(async () => {
    setLoadState('loading');
    setErrorMessage(null);
    try {
      const data = await getDashboardStats();
      setStats(data);
      setLoadState('success');
    } catch (err) {
      setErrorMessage(extractErrorMessage(err, 'Failed to load dashboard statistics.'));
      setLoadState('error');
    }
  }, []);

  useEffect(() => {
    void loadStats();
  }, [loadStats]);

  return (
    <div className={styles.shell}>
      <PageHeader
        title="Dashboard"
        subtitle={`Welcome back, ${user?.full_name ?? 'Admin'}`}
        breadcrumbs={[{ label: 'Admin' }, { label: 'Dashboard' }]}
      />

      <div className={styles.body}>
          {loadState === 'loading' && (
            <div className={styles.centered}>
              <LoadingSpinner size="lg" label="Loading dashboard…" />
              <p className={styles.loadingText}>Loading dashboard…</p>
            </div>
          )}

          {loadState === 'error' && (
            <ErrorState
              title="Failed to load dashboard"
              message={errorMessage ?? undefined}
              onRetry={loadStats}
            />
          )}

          {loadState === 'success' && stats && (
            <>
              {/* ── Provider inventory counters ───────────────────────── */}
              <section aria-labelledby="stats-heading">
                <h2 id="stats-heading" className={styles.sectionTitle}>Provider Inventory</h2>
                <div className={styles.statsGrid}>
                  <StatCard
                    label="Active providers"
                    value={String(stats.active_providers)}
                    icon="✓"
                    badge={{ label: 'Active', variant: 'success' }}
                  />
                  <StatCard
                    label="Hospitals"
                    value={String(stats.provider_counts.hospitals)}
                    icon="🏥"
                  />
                  <StatCard
                    label="Clinics"
                    value={String(stats.provider_counts.clinics)}
                    icon="🩺"
                  />
                  <StatCard
                    label="Doctors"
                    value={String(stats.provider_counts.doctors)}
                    icon="👨‍⚕️"
                  />
                </div>
              </section>

              <section aria-labelledby="activity-heading">
                <h2 id="activity-heading" className={styles.sectionTitle}>Activity overview</h2>
                <div className={styles.analyticsGrid}>
                  <InvitationStatusChart counts={stats.invitation_counts} />
                  <VisitorVisitsChart visits={stats.visitor_visits ?? []} />
                </div>
              </section>

              {/* ── Provider locations map ────────────────────────────── */}
              <section aria-labelledby="map-heading">
                <h2 id="map-heading" className={styles.sectionTitle}>Provider Locations</h2>
                <Card padding="md" shadow="sm">
                  <DashboardMap markers={stats.location_markers} />
                </Card>
              </section>

            </>
          )}
      </div>
    </div>
  );
}

// ── Sub-components ───────────────────────────────────────────────────────────

interface StatCardProps {
  label: string;
  value: string;
  icon: string;
  badge?: { label: string; variant: 'success' | 'info' | 'warning' | 'error' };
}

function StatCard({ label, value, icon, badge }: StatCardProps) {
  return (
    <Card padding="md" shadow="sm" className={styles.statCard}>
      <div className={styles.statIcon} aria-hidden="true">{icon}</div>
      <p className={styles.statValue}>{value}</p>
      <p className={styles.statLabel}>{label}</p>
      {badge && <Badge variant={badge.variant} size="sm">{badge.label}</Badge>}
    </Card>
  );
}
