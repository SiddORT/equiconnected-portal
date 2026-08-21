import type { DailyVisit } from '@/types';
import { Card } from '@/components/ui/Card';
import styles from './VisitorVisitsChart.module.css';

interface VisitorVisitsChartProps {
  visits: DailyVisit[];
}

function dayLabel(date: string): string {
  return new Intl.DateTimeFormat(undefined, { weekday: 'short' }).format(
    new Date(`${date}T12:00:00Z`),
  );
}

export function VisitorVisitsChart({ visits }: VisitorVisitsChartProps) {
  const chartVisits = visits.length === 7 ? visits : [];
  const maximum = Math.max(...chartVisits.map((visit) => visit.count), 1);
  const total = chartVisits.reduce((sum, visit) => sum + visit.count, 0);

  return (
    <Card padding="md" shadow="sm" className={styles.card}>
      <div className={styles.header}>
        <div>
          <h3 className={styles.title}>Website visits</h3>
          <p className={styles.subtitle}>Public website visits · last 7 days</p>
        </div>
        <strong className={styles.total}>{total}</strong>
      </div>
      <div
        className={styles.chart}
        role="img"
        aria-label={`${total} public website visits across the last seven days`}
      >
        {chartVisits.map((visit) => (
          <div key={visit.date} className={styles.column}>
            <span className={styles.count}>{visit.count}</span>
            <div className={styles.barArea} aria-hidden="true">
              <span
                className={styles.bar}
                style={{ height: `${(visit.count / maximum) * 100}%` }}
              />
            </div>
            <span className={styles.day}>{dayLabel(visit.date)}</span>
          </div>
        ))}
      </div>
    </Card>
  );
}