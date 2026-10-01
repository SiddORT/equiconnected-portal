import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from 'react';
import { Link } from 'react-router-dom';
import { getDashboardVisits } from '@/api/admin';
import { extractErrorMessage } from '@/api/client';
import type { DashboardVisit, DashboardVisitMonth } from '@/types';
import styles from './VisitingProviderCalendar.module.css';

const weekdays = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
const weekdayShort = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'];

export interface VisitingProviderCalendarProps {
  loadMonth?: (month?: string) => Promise<DashboardVisitMonth>;
  providerHref?: (id: string) => string;
  providerState?: unknown;
  returnHref?: string;
  returnState?: unknown;
  fullPage?: boolean;
  audience?: 'admin' | 'member';
}

function shiftMonth(month: string, offset: number): string {
  const [year, number] = month.split('-').map(Number);
  const index = year * 12 + number - 1 + offset;
  return `${String(Math.floor(index / 12)).padStart(4, '0')}-${String(index % 12 + 1).padStart(2, '0')}`;
}

function monthDays(month: string): { date: string; day: number }[] {
  const [year, number] = month.split('-').map(Number);
  const count = new Date(Date.UTC(year, number, 0)).getUTCDate();
  return Array.from({ length: count }, (_, i) => ({
    date: `${month}-${String(i + 1).padStart(2, '0')}`,
    day: i + 1,
  }));
}

function formatDate(date: string, options: Intl.DateTimeFormatOptions): string {
  return new Intl.DateTimeFormat('en-US', { ...options, timeZone: 'UTC' })
    .format(new Date(`${date}T12:00:00Z`));
}

function visitLocation(visit: DashboardVisit): string {
  return [
    visit.location.name,
    visit.location.city,
    visit.location.state_province,
    visit.location.country,
  ].filter(Boolean).join(', ') || 'Location not listed';
}

export function VisitingProviderCalendar({
  loadMonth = getDashboardVisits,
  providerHref = (id) => `/admin/providers/${id}`,
  providerState,
  returnHref,
  returnState,
  fullPage = false,
  audience = 'admin',
}: VisitingProviderCalendarProps) {
  const [requestedMonth, setRequestedMonth] = useState<string | undefined>();
  const [data, setData] = useState<DashboardVisitMonth | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [retry, setRetry] = useState(0);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const todayRef = useRef<string | null>(null);
  const requestId = useRef(0);
  const dayButtonRefs = useRef<Record<string, HTMLButtonElement | null>>({});
  const agendaRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    const id = ++requestId.current;
    setLoading(true);
    setError(null);
    void loadMonth(requestedMonth)
      .then((result) => {
        if (id !== requestId.current) return;
        todayRef.current = result.today;
        setData(result);
        setSelectedDate((current) => current && current.startsWith(result.month)
          ? current
          : result.today.startsWith(result.month) ? result.today : `${result.month}-01`);
      })
      .catch((err: unknown) => {
        if (id === requestId.current) {
          setError(extractErrorMessage(err, 'Could not load scheduled visits.'));
        }
      })
      .finally(() => {
        if (id === requestId.current) setLoading(false);
      });
    return () => { requestId.current += 1; };
  }, [loadMonth, requestedMonth, retry]);

  const shownMonth = requestedMonth ?? data?.month;
  const currentToday = data?.today ?? todayRef.current;
  const currentMonth = currentToday?.slice(0, 7);
  const days = useMemo(() => shownMonth ? monthDays(shownMonth) : [], [shownMonth]);
  const title = shownMonth
    ? formatDate(`${shownMonth}-01`, { month: 'long', year: 'numeric' })
    : 'Visiting providers';
  const firstWeekday = shownMonth
    ? new Date(`${shownMonth}-01T12:00:00Z`).getUTCDay()
    : 0;
  const visitsByDate = useMemo(() => {
    const map = new Map<string, DashboardVisit[]>();
    if (!data) return map;
    for (const { date } of days) {
      map.set(date, data.visits.filter((visit) => visit.start_date <= date && visit.end_date >= date));
    }
    return map;
  }, [data, days]);
  const activeDate = selectedDate && selectedDate.startsWith(shownMonth ?? '')
    ? selectedDate
    : currentToday?.startsWith(shownMonth ?? '') ? currentToday : days[0]?.date;
  const activeVisits = activeDate ? visitsByDate.get(activeDate) ?? [] : [];
  const previousDisabled = !shownMonth || !currentMonth || shownMonth <= currentMonth;
  const nextDisabled = !shownMonth || shownMonth === '9999-12';

  function chooseDay(date: string, focus = false) {
    setSelectedDate(date);
    if (focus) dayButtonRefs.current[date]?.focus();
  }

  function onDayKeyDown(event: KeyboardEvent<HTMLButtonElement>, date: string) {
    const offsets: Record<string, number> = {
      ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7,
    };
    if (event.key === 'Home' || event.key === 'End') {
      event.preventDefault();
      chooseDay(days[event.key === 'Home' ? 0 : days.length - 1].date, true);
      return;
    }
    const offset = offsets[event.key];
    if (offset === undefined) return;
    const index = days.findIndex((day) => day.date === date);
    const next = days[Math.max(0, Math.min(days.length - 1, index + offset))];
    if (next) {
      event.preventDefault();
      chooseDay(next.date, true);
    }
  }

  const returnPath = returnHref ?? (audience === 'admin' ? '/admin/dashboard' : '/providers');
  const sectionClass = `${styles.section} ${fullPage ? styles.fullPage : styles.compact}`;
  const heading = 'Visiting providers';
  const TitleTag = fullPage ? 'h1' : 'h2';

  return (
    <section className={sectionClass} aria-labelledby="visiting-providers-heading">
      {fullPage && (
        <div className={styles.eyebrow}>
          <span>TRAVEL & AVAILABILITY</span>
          <span className={styles.eyebrowRule} />
        </div>
      )}
      <div className={styles.intro}>
        <div>
          <TitleTag id="visiting-providers-heading" className={styles.title}>{heading}</TitleTag>
          {fullPage && <p className={styles.subtitle}>Find visiting care, day by day.</p>}
        </div>
        {fullPage && (
          <Link className={styles.returnLink} to={returnPath} state={returnState}>
            <span aria-hidden="true">←</span> {audience === 'admin' ? 'Dashboard' : 'Provider directory'}
          </Link>
        )}
      </div>

      <div className={styles.calendar}>
        <p className={styles.scheduleNote}>Scheduled visiting periods, not appointment slots or a guarantee of immediate availability. Contact the provider to confirm plans.</p>
        <header className={styles.header}>
          <div className={styles.monthBlock}>
            <span className={styles.monthLabel}>SCHEDULE</span>
            <h2 className={styles.month} aria-live="polite">
              {title === 'Visiting providers' ? 'Loading month…' : title}
            </h2>
          </div>
          <nav className={styles.controls} aria-label="Calendar month navigation">
            <button type="button" onClick={() => {
              if (currentMonth && currentToday) {
                setRequestedMonth(currentMonth);
                setSelectedDate(currentToday);
              }
            }}
              disabled={!currentMonth || (shownMonth === currentMonth && activeDate === currentToday)} className={styles.todayButton}>
              Today
            </button>
            <button type="button" aria-label="Previous month" disabled={previousDisabled}
              onClick={() => shownMonth && setRequestedMonth(shiftMonth(shownMonth, -1))}
              className={styles.arrowButton}><span aria-hidden="true">←</span></button>
            <button type="button" aria-label="Next month" disabled={nextDisabled}
              onClick={() => shownMonth && setRequestedMonth(shiftMonth(shownMonth, 1))}
              className={styles.arrowButton}><span aria-hidden="true">→</span></button>
          </nav>
        </header>

        {error && (
          <div role="alert" className={styles.error}>
            <div><strong>Schedule unavailable</strong><p>{error}</p></div>
            <button type="button" onClick={() => setRetry((value) => value + 1)}>Try again</button>
          </div>
        )}
        {loading && !error && (
          <div role="status" className={styles.loading}>
            <span className={styles.skeletonLine} />
            <span>Loading scheduled visits…</span>
          </div>
        )}

        {data && data.month === shownMonth && !error && !loading && (
          <>
            {data.visits.length === 0 && (
              <div className={styles.empty}>
                <span className={styles.emptyMark} aria-hidden="true">—</span>
                <div><h3>A quiet month</h3><p>No visiting providers scheduled this month.</p></div>
              </div>
            )}
            <div className={styles.monthLayout}>
              <div className={styles.desktopCalendar} role="group" aria-label={`${title} date selection`}>
                <div className={styles.weekHeader} aria-hidden="true">
                  {weekdayShort.map((day, index) => <span key={day} title={weekdays[index]}>{day}</span>)}
                </div>
                <div className={styles.monthGrid}>
                  {Array.from({ length: firstWeekday }, (_, i) => (
                    <span key={`blank-${i}`} className={styles.blank} aria-hidden="true" />
                  ))}
                  {days.map(({ date, day }) => {
                    const visits = visitsByDate.get(date) ?? [];
                    return (
                      <button key={date} ref={(node) => { dayButtonRefs.current[date] = node; }}
                        type="button" className={`${styles.day} ${date === currentToday ? styles.today : ''} ${date === activeDate ? styles.selected : ''}`}
                        aria-label={`${formatDate(date, { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })}, ${visits.length} ${visits.length === 1 ? 'visiting provider' : 'visiting providers'}`}
                        aria-current={date === currentToday ? 'date' : undefined}
                        aria-pressed={date === activeDate}
                        tabIndex={date === activeDate ? 0 : -1}
                        onClick={() => chooseDay(date)}
                        onKeyDown={(event) => onDayKeyDown(event, date)}>
                        <span className={styles.dayNumber}>{day}</span>
                        {visits.length > 0 && (
                          <span className={styles.daySummary}>
                            <span className={styles.visitDot} />
                            {visits.length} {visits.length === 1 ? 'visit' : 'visits'}
                          </span>
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>
              <aside ref={agendaRef} className={styles.agenda} aria-labelledby="agenda-heading">
                <div className={styles.agendaHeading}>
                  <div>
                    <span className={styles.agendaKicker}>DAY AGENDA</span>
                    <h3 id="agenda-heading" aria-live="polite">{activeDate
                      ? formatDate(activeDate, { weekday: 'long', month: 'long', day: 'numeric' })
                      : 'Choose a date'}</h3>
                  </div>
                  <span className={styles.count}>{activeVisits.length.toString().padStart(2, '0')}</span>
                </div>
                <div className={styles.mobileDates} role="group" aria-label="Choose a day">
                  {days.filter(({ date }) => (visitsByDate.get(date)?.length ?? 0) > 0 || date === currentToday)
                    .map(({ date, day }) => (
                      <button key={date} type="button" onClick={() => {
                        chooseDay(date);
                        agendaRef.current?.scrollIntoView?.({ block: 'start' });
                      }}
                        aria-pressed={date === activeDate} aria-current={date === currentToday ? 'date' : undefined}
                        className={`${styles.mobileDate} ${date === activeDate ? styles.mobileDateActive : ''}`}>
                        <span>{formatDate(date, { weekday: 'short' })}</span><strong>{day}</strong>
                        <small>{visitsByDate.get(date)?.length ?? 0}</small>
                      </button>
                    ))}
                </div>
                <div className={styles.visitList}>
                  {activeVisits.length === 0 ? (
                    <p className={styles.dayEmpty}>Nothing scheduled for this day.</p>
                  ) : activeVisits.map((visit) => (
                    <Link key={visit.id} to={providerHref(visit.provider_id)} state={providerState} className={styles.visitCard}
                      aria-label={`${visit.provider_name}, ${visit.specializations.join(', ') || 'Expertise not listed'}, ${visitLocation(visit)}, ${activeDate}`}>
                      <span className={styles.visitDate}>
                        {visit.start_date === visit.end_date
                          ? 'One day'
                          : `${formatDate(visit.start_date, { month: 'short', day: 'numeric' })} – ${formatDate(visit.end_date, { month: 'short', day: 'numeric' })}`}
                      </span>
                      <strong className={styles.providerName}>{visit.provider_name}</strong>
                      <span className={styles.specialty}>{visit.specializations.join(' · ') || 'Expertise not listed'}</span>
                      <span className={styles.location}>{visitLocation(visit)}</span>
                      <span className={styles.profileAction}>Provider profile <span aria-hidden="true">↗</span></span>
                    </Link>
                  ))}
                </div>
              </aside>
              <div className={styles.mobileDayList} role="group" aria-label={`${title} date selection`}>
                {days.map(({ date, day }) => {
                  const visits = visitsByDate.get(date) ?? [];
                  return (
                    <button key={date} type="button" onClick={() => chooseDay(date)}
                      aria-pressed={date === activeDate} aria-current={date === currentToday ? 'date' : undefined}
                      className={`${styles.mobileDay} ${date === activeDate ? styles.mobileDayActive : ''}`}>
                      <span className={styles.mobileDayDate}>
                        <small>{formatDate(date, { weekday: 'short' })}</small><strong>{day}</strong>
                      </span>
                      <span className={styles.mobileDaySummary}>{visits.length
                        ? `${visits.length} ${visits.length === 1 ? 'provider' : 'providers'}`
                        : 'No visits'}</span>
                      {date === currentToday && <span className={styles.todayTag}>Today</span>}
                    </button>
                  );
                })}
              </div>
            </div>
          </>
        )}
      </div>
    </section>
  );
}