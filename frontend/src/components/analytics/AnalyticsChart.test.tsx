import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { AnalyticsChart } from './AnalyticsChart';

describe('AnalyticsChart', () => {
  it('reads provider-specific count fields instead of plotting unavailable zeroes', () => {
    render(<AnalyticsChart title="Most-reviewed providers" group={[
      { name: 'Pine Ridge', rating_count: 18 },
      { name: 'Cedar Run', rating_count: 11 },
    ]} unit="eligible ratings" />);

    expect(screen.getByRole('img', { name: /Pine Ridge: 18 eligible ratings/ })).toBeTruthy();
    expect(screen.getAllByText('Pine Ridge').length).toBeGreaterThan(0);
    expect(screen.getAllByText('18').length).toBeGreaterThan(0);
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
    expect(screen.getByRole('table', { name: 'Monthly registrations data' })).toBeTruthy();
  });
});