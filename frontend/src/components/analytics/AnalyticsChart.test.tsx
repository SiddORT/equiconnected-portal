import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { AnalyticsChart } from './AnalyticsChart';

afterEach(cleanup);

describe('AnalyticsChart', () => {
  it('reads provider-specific count fields instead of plotting unavailable zeroes', () => {
    render(<AnalyticsChart title="Most-reviewed providers" group={[
      { name: 'Pine Ridge', rating_count: 18 },
      { name: 'Cedar Run', rating_count: 11 },
    ]} unit="eligible ratings" />);

    expect(screen.getByRole('img', { name: /Pine Ridge: 18 eligible ratings/ })).toBeTruthy();
    expect(screen.queryByRole('table', { name: 'Most-reviewed providers data' })).toBeNull();
    expect(document.querySelector('details')?.hasAttribute('open')).toBe(false);
    expect(screen.queryByText('Unavailable')).toBeNull();
  });

  it('plots date buckets at elapsed-time positions and labels the numeric axis', () => {
    render(<AnalyticsChart title="Monthly registrations" kind="trend" unit="members" points={[
      { bucket: '2026-01-01', value: 10 },
      { bucket: '2026-01-15', value: 15 },
      { bucket: '2026-04-01', value: 30 },
    ]} />);

    const marks = screen.getByRole('img', { name: /Monthly registrations/ }).querySelectorAll('circle');
    const earlyJanuary = Number(marks[1].getAttribute('cx'));
    expect(earlyJanuary).toBeLessThan(180);
    expect(screen.getByText('30', { selector: 'text' })).toBeTruthy();
    expect(screen.queryByRole('table', { name: 'Monthly registrations data' })).toBeNull();
  });

  it('uses the data table as the accessible chart alternative when opened', async () => {
    const rendered = render(<AnalyticsChart title="Visits" points={[{ bucket: 'Monday', value: 12 }]} />);
    expect(screen.getByRole('img', { name: /Visits/ })).toBeTruthy();
    fireEvent.click(rendered.container.querySelector('details summary')!);
    await waitFor(() => expect(screen.getByRole('table', { name: 'Visits data' })).toBeTruthy());
    expect(screen.queryByRole('img', { name: /Visits/ })).toBeNull();
  });

  it('keeps metric definitions collapsed until requested', async () => {
    const rendered = render(<AnalyticsChart title="Visits" definition="Tracked profile page views." points={[]} />);
    expect(rendered.container.querySelector('details')?.hasAttribute('open')).toBe(false);
    fireEvent.click(screen.getByText('How this is counted'));
    await waitFor(() => expect(screen.getByText('Tracked profile page views.')).toBeTruthy());
  });
});