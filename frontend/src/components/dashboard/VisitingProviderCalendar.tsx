import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { getDashboardVisits } from '@/api/admin';
import { extractErrorMessage } from '@/api/client';
import { Card } from '@/components/ui/Card';
import type { DashboardVisitMonth } from '@/types';
import styles from './VisitingProviderCalendar.module.css';

const weekdays = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

function shiftMonth(month: string, offset: number): string {
  const [year, number] = month.split('-').map(Number);
  const index = year * 12 + number - 1 + offset;
  return `${String(Math.floor(index / 12)).padStart(4, '0')}-${String(index % 12 + 1).padStart(2, '0')}`;
}

function monthDays(month: string): { date: string; day: number }[] {
  const number = Number(month.slice(5));
  const last = new Date(`${month}-01T12:00:00Z`);
  last.setUTCMonth(number);
  last.setUTCDate(0);
  const count = last.getUTCDate();
  return Array.from({ length: count }, (_, i) => ({
    date: `${month}-${String(i + 1).padStart(2, '0')}`,
    day: i + 1,
  }));
}

export function VisitingProviderCalendar() {
  const [month, setMonth] = useState<string | null>(null);
  const [data, setData] = useState<DashboardVisitMonth | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);
  const todayRef = useRef<string | null>(null);

  useEffect(() => {
    let active = true;
    setData(null);
    setError(null);
    void getDashboardVisits(month ?? undefined)
      .then((result) => {
        if (!active) return;
        todayRef.current = result.today;
        setData(result);
      })
      .catch((err) => {
        if (active) setError(extractErrorMessage(err, 'Could not load scheduled visits.'));
      });
    return () => { active = false; };
  }, [month, retry]);

  const shownMonth = month ?? data?.month;
  // Keep the server's system-calendar date across month requests, not the browser's local date.
  const currentToday = data?.today ?? todayRef.current;
  const currentMonth = currentToday?.slice(0, 7);
  const days = shownMonth ? monthDays(shownMonth) : [];
  const firstWeekday = shownMonth
    ? new Date(`${shownMonth}-01T12:00:00Z`).getUTCDay()
    : 0;
  const title = shownMonth
    ? new Intl.DateTimeFormat('en-US', { month: 'long', year: 'numeric', timeZone: 'UTC' })
      .format(new Date(`${shownMonth}-01T12:00:00Z`))
    : 'Visiting providers';

  return (
    <section className={styles.section} aria-labelledby="visiting-providers-heading">
      <h2 id="visiting-providers-heading" className={styles.title}>Visiting providers</h2>
      <Card padding="md" shadow="sm" className={styles.calendar}>
        <div className={styles.header}>
          <p className={styles.month} aria-live="polite">{title === 'Visiting providers' ? 'Loading month…' : title}</p>
          <div className={styles.controls}>
            <button type="button" onClick={() => setMonth(currentMonth ?? null)}
              disabled={!currentMonth || shownMonth === currentMonth}>Today</button>
            <button type="button" aria-label="Previous month"
              disabled={!shownMonth || !currentMonth || shownMonth <= currentMonth}
              onClick={() => setMonth(shiftMonth(shownMonth!, -1))}>‹</button>
            <button type="button" aria-label="Next month"
              disabled={!shownMonth || shownMonth === '9999-12'}
              onClick={() => setMonth(shiftMonth(shownMonth!, 1))}>›</button>
          </div>
        </div>
        {error && (
          <div role="alert" className={styles.message}>
            <p>{error}</p>
            <button type="button" onClick={() => setRetry((value) => value + 1)}>Retry visits</button>
          </div>
        )}
        {!data && !error && <p role="status" className={styles.message}>Loading scheduled visits…</p>}
        {data && shownMonth && (
          <>
            {data.visits.length === 0 && <p className={styles.message}>No visiting providers scheduled this month.</p>}
            <div className={styles.grid} role="grid" aria-label={`${title} visiting provider calendar`}>
              {weekdays.map((day) => <span key={day} className={styles.weekday} role="columnheader">{day}</span>)}
              {Array.from({ length: firstWeekday }, (_, i) => <span key={`blank-${i}`} className={styles.blank} aria-hidden="true" />)}
              {days.map(({ date, day }) => {
                const visits = data.visits.filter((visit) => visit.start_date <= date && visit.end_date >= date);
                return (
                  <div key={date} role="gridcell" aria-label={`${date}, ${visits.length} visiting ${visits.length === 1 ? 'provider' : 'providers'}`}
                    aria-current={date === currentToday ? 'date' : undefined}
                    className={`${styles.day} ${date === currentToday ? styles.today : ''}`}>
                    <span className={styles.dayNumber}>{day}</span>
                    <div className={styles.entries}>
                      {visits.map((visit) => (
                        <Link key={visit.id} to={`/admin/providers/${visit.provider_id}`}
                          className={styles.entry}
                          aria-label={`${visit.provider_name}, ${visit.specializations.join(', ') || 'Expertise not listed'}, ${[visit.location.name, visit.location.city].filter(Boolean).join(', ') || 'Location not listed'}, ${date}`}>
                          <strong>{visit.provider_name}</strong>
                          <span>{visit.specializations.join(', ') || 'Expertise not listed'}</span>
                          <span>{[visit.location.name, visit.location.city].filter(Boolean).join(', ') || 'Location not listed'}</span>
                        </Link>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </>
        )}
      </Card>
    </section>
  );
}