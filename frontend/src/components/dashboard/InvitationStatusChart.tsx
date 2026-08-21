import type { InvitationCounts } from '@/types';
import { Card } from '@/components/ui/Card';
import styles from './InvitationStatusChart.module.css';

interface InvitationStatusChartProps {
  counts: InvitationCounts;
}

const chartItems = [
  {
    key: 'sent',
    label: 'Invitations sent',
    detail: 'All invitations',
    className: 'sent',
  },
  {
    key: 'accepted',
    label: 'Accepted',
    detail: 'Accepted or completed',
    className: 'accepted',
  },
  {
    key: 'rejected',
    label: 'Rejected',
    detail: 'Cancelled or expired',
    className: 'rejected',
  },
] as const;

export function InvitationStatusChart({ counts }: InvitationStatusChartProps) {
  const highestValue = Math.max(counts.sent, counts.accepted, counts.rejected, 1);
  const chartSummary = `Invitations: ${counts.sent} sent, ${counts.accepted} accepted, and ${counts.rejected} rejected or expired.`;

  return (
    <Card padding="md" shadow="sm" className={styles.card}>
      <div className={styles.header}>
        <div>
          <h3 className={styles.title}>Invitation activity</h3>
          <p className={styles.subtitle}>Invitation progress across all time</p>
        </div>
      </div>
      <div className={styles.chart} role="img" aria-label={chartSummary}>
        {chartItems.map((item) => {
          const value = counts[item.key];
          const width = `${(value / highestValue) * 100}%`;
          return (
            <div key={item.key} className={styles.item}>
              <div className={styles.labelRow}>
                <div>
                  <p className={styles.label}>{item.label}</p>
                  <p className={styles.detail}>{item.detail}</p>
                </div>
                <strong className={styles.value}>{value}</strong>
              </div>
              <div className={styles.track} aria-hidden="true">
                <div className={`${styles.bar} ${styles[item.className]}`} style={{ width }} />
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}