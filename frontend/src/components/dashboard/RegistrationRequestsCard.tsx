import type { RegistrationCounts } from '@/types';
import { Card } from '@/components/ui/Card';
import styles from './RegistrationRequestsCard.module.css';

interface RegistrationRequestsCardProps {
  counts: RegistrationCounts;
}

export function RegistrationRequestsCard({ counts }: RegistrationRequestsCardProps) {
  const summary = [
    `${counts.registrations} registrations`,
    `${counts.verified} verified`,
    `${counts.unverified} unverified`,
    `${counts.horse_owners} horse owners`,
    `${counts.stable_managers} stable managers`,
  ].join(', ');

  return (
    <Card padding="md" shadow="sm" className={styles.card}>
      <div className={styles.header}>
        <div>
          <h3 className={styles.title}>Member registrations</h3>
          <p className={styles.subtitle}>Public account signups across all time</p>
        </div>
        <strong className={styles.total}>{counts.registrations}</strong>
      </div>

      <div className={styles.metrics} role="img" aria-label={summary}>
        <div className={styles.metric}>
          <span>Verified</span>
          <strong className={styles.verified}>{counts.verified}</strong>
        </div>
        <div className={styles.metric}>
          <span>Unverified</span>
          <strong className={styles.unverified}>{counts.unverified}</strong>
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

      <p className={styles.note}>Email verification unlocks member access.</p>
    </Card>
  );
}