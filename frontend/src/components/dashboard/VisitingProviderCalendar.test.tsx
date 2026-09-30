import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { readFileSync } from 'node:fs';
import { getDashboardVisits } from '@/api/admin';
import type { DashboardVisitMonth } from '@/types';
import { VisitingProviderCalendar } from './VisitingProviderCalendar';

vi.mock('@/api/admin', () => ({ getDashboardVisits: vi.fn() }));

const september: DashboardVisitMonth = {
  month: '2026-09', today: '2026-09-24',
  visits: [
    {
      id: 'trip-1', provider_id: 'doctor-1', provider_name: 'Dr. Maple',
      start_date: '2026-09-24', end_date: '2026-10-02', specializations: ['Surgery'],
      location: { name: 'North paddock', city: 'Calgary' },
    },
    {
      id: 'trip-2', provider_id: 'doctor-2', provider_name: 'Dr. Birch',
      start_date: '2026-09-24', end_date: '2026-09-24', specializations: [],
      location: { city: 'Edmonton' },
    },
  ],
};

function renderCalendar() {
  return render(
    <MemoryRouter initialEntries={['/admin/dashboard']}>
      <Routes>
        <Route path="/admin/dashboard" element={<VisitingProviderCalendar />} />
        <Route path="/admin/providers/:id" element={<p>Provider detail opened</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

describe('VisitingProviderCalendar', () => {
  it('loads the system month, shows all visits on their inclusive dates, and links to detail', async () => {
    vi.mocked(getDashboardVisits).mockResolvedValue(september);
    renderCalendar();
    expect(await screen.findByText('September 2026')).toBeTruthy();
    const heading = screen.getByRole('heading', { name: 'Visiting providers' });
    expect(heading.parentElement?.tagName).toBe('SECTION');
    expect(heading.parentElement?.querySelector('[role="grid"]')).toBeTruthy();
    expect(getDashboardVisits).toHaveBeenCalledWith(undefined);
    const today = screen.getByRole('gridcell', { name: '2026-09-24, 2 visiting providers' });
    expect(today.getAttribute('aria-current')).toBe('date');
    expect(within(today).getAllByRole('link')).toHaveLength(2);
    expect(within(today).getByRole('link', { name: /Dr. Maple, Surgery, North paddock, Calgary/ })
      .getAttribute('href')).toBe('/admin/providers/doctor-1');
    expect(within(today).getByRole('link', { name: /Dr. Birch, Expertise not listed, Edmonton/ })).toBeTruthy();
    expect(within(screen.getByRole('gridcell', { name: '2026-09-30, 1 visiting provider' }))
      .getAllByRole('link')).toHaveLength(1);
    await userEvent.setup().click(within(today).getByRole('link', { name: /Dr. Maple/ }));
    expect(await screen.findByText('Provider detail opened')).toBeTruthy();
  });

  it('moves through upcoming months and returns to the server current month', async () => {
    vi.mocked(getDashboardVisits).mockImplementation(async (month) => month === '2026-10'
      ? { ...september, month: '2026-10', visits: [september.visits[0]] }
      : september);
    renderCalendar();
    await screen.findByText('September 2026');
    expect(screen.getByRole('button', { name: 'Previous month' }).hasAttribute('disabled')).toBe(true);
    await userEvent.setup().click(screen.getByRole('button', { name: 'Next month' }));
    expect(await screen.findByText('October 2026')).toBeTruthy();
    expect(getDashboardVisits).toHaveBeenCalledWith('2026-10');
    expect(within(screen.getByRole('gridcell', { name: '2026-10-02, 1 visiting provider' }))
      .getByRole('link', { name: /Dr. Maple/ })).toBeTruthy();
    await userEvent.setup().click(screen.getByRole('button', { name: 'Today' }));
    await waitFor(() => expect(getDashboardVisits).toHaveBeenLastCalledWith('2026-09'));
    expect(await screen.findByText('September 2026')).toBeTruthy();
  });

  it('shows empty, loading, and retryable error states without losing navigation', async () => {
    vi.mocked(getDashboardVisits)
      .mockResolvedValueOnce({ ...september, visits: [] })
      .mockRejectedValueOnce(new Error('Visit feed unavailable'))
      .mockResolvedValueOnce({ ...september, month: '2026-10', visits: [] });
    renderCalendar();
    expect(screen.getByRole('status').textContent).toContain('Loading');
    expect(await screen.findByText('No visiting providers scheduled this month.')).toBeTruthy();
    await userEvent.setup().click(screen.getByRole('button', { name: 'Next month' }));
    expect(await screen.findByRole('alert')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Retry visits' })).toBeTruthy();
    await userEvent.setup().click(screen.getByRole('button', { name: 'Retry visits' }));
    expect(await screen.findByText('October 2026')).toBeTruthy();
    expect(screen.getByText('No visiting providers scheduled this month.')).toBeTruthy();
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('keeps a two-by-two inventory beside the calendar only at wide widths', () => {
    const css = readFileSync('src/pages/admin/DashboardPage.module.css', 'utf8');
    expect(css).toMatch(/\.overview\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*2fr\)\s+minmax\(0,\s*3fr\)/);
    expect(css).toMatch(/\.statsGrid\s*\{[^}]*grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\)/);
    expect(css).toMatch(/@media\s*\(max-width:\s*1100px\)\s*\{\s*\.overview\s*\{\s*grid-template-columns:\s*minmax\(0,\s*1fr\)/);
    const calendarCss = readFileSync('src/components/dashboard/VisitingProviderCalendar.module.css', 'utf8');
    expect(calendarCss).toContain('grid-template-columns: repeat(7, minmax(0, 1fr))');
    expect(calendarCss).toContain('overflow-wrap: anywhere');
  });
});