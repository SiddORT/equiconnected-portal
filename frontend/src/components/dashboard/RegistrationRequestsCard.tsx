import type { RegistrationCounts } from '@/types';
import { Card } from '@/components/ui/Card';
import styles from './RegistrationRequestsCard.module.css';

interface RegistrationRequestsCardProps {
  counts: RegistrationCounts;
}

export function RegistrationRequestsCard({ counts }: RegistrationRequestsCardProps) {
  const summary = [
    `${counts.requests} registration requests`,
    `${counts.approved} approved`,
    `${counts.rejected} rejected`,
    `${counts.horse_owners} horse owners`,
    `${counts.stable_managers} stable managers`,
  ].join(', ');

  return (
    <Card padding="md" shadow="sm" className={styles.card}>
      <div className={styles.header}>
        <div>
          <h3 className={styles.title}>Registration requests</h3>
          <p className={styles.subtitle}>Public account signups across all time</p>
        </div>
        <strong className={styles.total}>{counts.requests}</strong>
      </div>

      <div className={styles.metrics} role="img" aria-label={summary}>
        <div className={styles.metric}>
          <span>Approved</span>
          <strong className={styles.approved}>{counts.approved}</strong>
        </div>
        <div className={styles.metric}>
          <span>Rejected</span>
          <strong className={styles.rejected}>{counts.rejected}</strong>
        </div>
      </div>

      <div className={styles.roles}>
        <div>
          <span>Horse owners</span>
          <strong>{counts.horse_owners}</strong>
        </div>
        <div>
          <span>Stable managers</span>
          <strong>{counts.stable_managers}</strong>
        </div>
      </div>

      <p className={styles.note}>Approved after email verification.</p>
    </Card>
  );
}