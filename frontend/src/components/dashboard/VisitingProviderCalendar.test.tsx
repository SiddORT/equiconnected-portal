import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { readFileSync } from 'node:fs';
import type { DashboardVisitMonth } from '@/types';
import { VisitingProviderCalendar } from './VisitingProviderCalendar';

const september: DashboardVisitMonth = {
  month: '2026-09', today: '2026-09-24',
  visits: [
    {
      id: 'trip-1', provider_id: 'doctor-1', provider_name: 'Dr. Maple',
      start_date: '2026-09-24', end_date: '2026-10-02', specializations: ['Equine surgery'],
      location: { name: 'North paddock', city: 'Calgary', state_province: 'Alberta', country: 'Canada' },
    },
    {
      id: 'trip-2', provider_id: 'doctor-2', provider_name: 'Dr. Birch',
      start_date: '2026-09-24', end_date: '2026-09-24', specializations: [],
      location: { city: 'Edmonton', state_province: 'Alberta', country: 'Canada' },
    },
  ],
};

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllEnvs();
});

function renderCalendar(loadMonth: (month?: string) => Promise<DashboardVisitMonth>) {
  return render(
    <MemoryRouter initialEntries={['/admin/dashboard']}>
      <Routes>
        <Route path="/admin/dashboard" element={<VisitingProviderCalendar loadMonth={loadMonth} />} />
        <Route path="/admin/providers/:id" element={<p>Provider detail opened</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('VisitingProviderCalendar', () => {
  it('uses the server system date, includes both range boundaries, and shows the full day agenda', async () => {
    const loader = vi.fn().mockImplementation(async (month?: string) =>
      month === '2026-10' ? { ...september, month: '2026-10' } : september);
    renderCalendar(loader);
    expect(await screen.findByRole('heading', { name: 'September 2026' })).toBeTruthy();
    expect(loader).toHaveBeenCalledWith(undefined);

    const today = screen.getByRole('button', { name: /Thursday, September 24, 2026, 2 visiting providers/ });
    expect(today.getAttribute('aria-current')).toBe('date');
    expect(today.getAttribute('aria-pressed')).toBe('true');
    const agenda = screen.getByRole('complementary');
    expect(within(agenda).getByRole('link', { name: /Dr. Maple, Equine surgery, North paddock, Calgary, Alberta, Canada/ })).toBeTruthy();
    expect(within(agenda).getByRole('link', { name: /Dr. Birch, Expertise not listed, Edmonton, Alberta, Canada/ })).toBeTruthy();
    await userEvent.setup().click(screen.getByRole('button', { name: /Wednesday, September 30, 2026, 1 visiting provider/ }));
    expect(within(agenda).getByRole('link', { name: /Dr. Maple/ })).toBeTruthy();
    await userEvent.setup().click(screen.getByRole('button', { name: 'Today' }));
    expect(screen.getByRole('heading', { name: 'Thursday, September 24' })).toBeTruthy();
    await userEvent.setup().click(screen.getByRole('button', { name: 'Next month' }));
    await screen.findByRole('heading', { name: 'October 2026' });
    await userEvent.setup().click(screen.getByRole('button', { name: /Friday, October 2, 2026, 1 visiting provider/ }));
    expect(screen.getByRole('button', { name: /Friday, October 2, 2026/ })).toBeTruthy();

    await userEvent.setup().click(screen.getByRole('link', { name: /Dr. Maple/ }));
    expect(await screen.findByText('Provider detail opened')).toBeTruthy();
  });

  it('supports keyboard day selection with a crowded agenda and standard date movement', async () => {
    const visits = Array.from({ length: 9 }, (_, index) => ({
      id: `crowd-${index}`, provider_id: `provider-${index}`, provider_name: `Provider ${index + 1}`,
      start_date: '2026-09-24', end_date: '2026-09-24',
      specializations: [`Specialty ${index + 1}`],
      location: { city: 'Calgary', state_province: 'Alberta', country: 'Canada' },
    }));
    const loader = vi.fn().mockResolvedValue({ ...september, visits });
    renderCalendar(loader);
    await screen.findByRole('heading', { name: 'September 2026' });
    const current = screen.getByRole('button', { name: /Thursday, September 24, 2026, 9 visiting providers/ });
    current.focus();
    await userEvent.setup().keyboard('{ArrowRight}');
    expect(document.activeElement).toBe(screen.getByRole('button', { name: /Friday, September 25, 2026/ }));
    expect(screen.getByRole('heading', { name: 'Friday, September 25' })).toBeTruthy();
    await userEvent.setup().keyboard('{ArrowLeft}');
    expect(document.activeElement).toBe(current);
    expect(screen.getAllByRole('link', { name: /Provider \d+, Specialty \d+/ })).toHaveLength(9);
  });

  it('loads Today from server date even when the runtime timezone crosses a month boundary', async () => {
    vi.stubEnv('TZ', 'Pacific/Kiritimati');
    const result = { month: '2027-01', today: '2027-01-01', visits: [] };
    const loader = vi.fn().mockImplementation(async (month?: string) =>
      month === '2027-02' ? { ...result, month: '2027-02' } : result);
    renderCalendar(loader);
    expect(await screen.findByRole('heading', { name: 'January 2027' })).toBeTruthy();
    expect(screen.getByRole('button', { name: /Friday, January 1, 2027, 0 visiting providers/ })
      .getAttribute('aria-current')).toBe('date');
    await userEvent.setup().click(screen.getByRole('button', { name: 'Next month' }));
    expect(await screen.findByRole('heading', { name: 'February 2027' })).toBeTruthy();
    await userEvent.setup().click(screen.getByRole('button', { name: 'Today' }));
    expect(await screen.findByRole('heading', { name: 'January 2027' })).toBeTruthy();
    expect(loader).toHaveBeenLastCalledWith('2027-01');
  });

  it('recovers on retry and ignores a stale response from the prior month', async () => {
    let resolveOctober!: (value: DashboardVisitMonth) => void;
    const loader = vi.fn()
      .mockResolvedValueOnce(september)
      .mockImplementationOnce(() => new Promise((resolve) => { resolveOctober = resolve; }))
      .mockResolvedValueOnce({ ...september, month: '2026-11', visits: [] })
      .mockRejectedValueOnce(new Error('The connection dropped'))
      .mockResolvedValueOnce({ ...september, month: '2026-12', visits: [] });
    renderCalendar(loader);
    await screen.findByRole('heading', { name: 'September 2026' });
    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'Next month' }));
    await user.click(screen.getByRole('button', { name: 'Next month' }));
    expect(await screen.findByRole('heading', { name: 'November 2026' })).toBeTruthy();
    resolveOctober({ ...september, month: '2026-10', visits: [september.visits[0]] });
    await waitFor(() => expect(screen.queryByRole('heading', { name: 'October 2026' })).toBeNull());
    await user.click(screen.getByRole('button', { name: 'Next month' }));
    expect(await screen.findByRole('alert')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Try again' })).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'Try again' }));
    expect(await screen.findByRole('heading', { name: 'December 2026' })).toBeTruthy();
    expect(screen.getByText('No visiting providers scheduled this month.')).toBeTruthy();
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('keeps the month navigation and date controls accessible without a pretend ARIA grid', async () => {
    renderCalendar(vi.fn().mockResolvedValue(september));
    await screen.findByRole('heading', { name: 'September 2026' });
    expect(screen.queryByRole('grid')).toBeNull();
    expect(screen.getByRole('navigation', { name: 'Calendar month navigation' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Today' })).toBeTruthy();
  });

  it('keeps calendar CSS warm-toned and responsive', () => {
    const calendarCss = readFileSync('src/components/dashboard/VisitingProviderCalendar.module.css', 'utf8');
    expect(calendarCss).toContain('grid-template-columns: repeat(7, minmax(0, 1fr))');
    expect(calendarCss).toContain('overflow-wrap: anywhere');
    expect(calendarCss).toContain('#f7f3e9');
    expect(calendarCss).toContain('.mobileDayList { display: flex');
  });
});