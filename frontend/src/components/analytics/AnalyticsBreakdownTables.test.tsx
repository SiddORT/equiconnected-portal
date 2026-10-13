import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import type { AnalyticsBreakdowns } from '@/types/analytics';
import { AnalyticsBreakdownTables } from './AnalyticsBreakdownTables';

const reports = [{
  domain: 'providers',
  timezone: 'UTC',
  period: { preset: 'last_30_days', date_from: null, date_to: null, group_by: 'daily' },
  coverage: { available: true },
  definitions: { top_reviewed_providers: 'Eligible providers by current rating count.' },
  groups: {
    top_reviewed_providers: [{ name: 'Northwind Stables', rating_count: 14 }],
    provider_status: { active: 8, inactive: 3 },
  },
}] as unknown as AnalyticsBreakdowns[];

afterEach(cleanup);

it.each([
  { group: { HORSE_OWNER: 3 } },
  { group: [{ type: 'HORSE_OWNER', count: 3 }] },
])('shows Horse Owner in subscriber breakdown tables', ({ group }) => {
  const report = { ...reports[0], domain: 'subscribers', groups: { subscriber_type: group } } as AnalyticsBreakdowns;
  render(<AnalyticsBreakdownTables reports={[report]} />);
  fireEvent.click(screen.getByText('subscribers · subscriber type'));
  expect(screen.getByRole('rowheader', { name: 'Horse Owner' })).toBeTruthy();
  expect(screen.queryByText('HORSE_OWNER')).toBeNull();
});

describe('AnalyticsBreakdownTables', () => {
  it('starts collapsed and reveals a group definition and values on demand', async () => {
    const rendered = render(<AnalyticsBreakdownTables reports={reports} />);
    expect(rendered.container.querySelector('details')?.hasAttribute('open')).toBe(false);
    expect(screen.queryByRole('table')).toBeNull();
    fireEvent.click(screen.getByText('providers · provider status'));
    await waitFor(() => expect(screen.getByText('Aggregate count for provider status.')).toBeTruthy());
    expect(screen.getByRole('table', { name: 'providers provider_status aggregate values' })).toBeTruthy();
  });

  it('omits named top-level groups already represented by a curated chart', () => {
    render(<AnalyticsBreakdownTables reports={reports} excludedGroupNames={['top_reviewed_providers']} />);
    expect(screen.queryByText(/top reviewed providers/)).toBeNull();
    expect(screen.getByText('providers · provider status')).toBeTruthy();
  });

  it('shows supplied null count metrics as Unavailable without fabricating absent fields', async () => {
    const nullMetricReport = [{
      ...reports[0],
      groups: {
        provider_views: [{ provider_name: 'Northwind Stables', profile_views: null, review_submissions: 7 }],
      },
    }] as unknown as AnalyticsBreakdowns[];
    render(<AnalyticsBreakdownTables reports={nullMetricReport} title="Traffic detail" variant="metrics" />);
    expect(screen.getByRole('heading', { name: 'Traffic detail' })).toBeTruthy();
    const disclosure = screen.getByText('providers · provider views').closest('summary')!;
    disclosure.focus();
    expect(document.activeElement).toBe(disclosure);
    fireEvent.keyDown(disclosure, { key: 'Enter' });
    expect(await screen.findByText('Unavailable')).toBeTruthy();
    expect(screen.getByRole('columnheader', { name: 'Value' })).toBeTruthy();
    expect(screen.getByText('Northwind Stables · review submissions')).toBeTruthy();
    expect(screen.queryByText(/saved count/i)).toBeNull();
    expect(screen.getAllByText('Aggregate report').length).toBeGreaterThan(0);
  });

  it('assigns unique section heading IDs when multiple tables render together', () => {
    const { container } = render(<><AnalyticsBreakdownTables reports={reports} /><AnalyticsBreakdownTables reports={reports} title="Second detail" /></>);
    const sections = container.querySelectorAll('section');
    const headingIds = Array.from(sections, (section) => section.querySelector('h2')?.id);
    expect(headingIds[0]).not.toBe(headingIds[1]);
    expect(sections[0].getAttribute('aria-labelledby')).toBe(headingIds[0]);
    expect(sections[1].getAttribute('aria-labelledby')).toBe(headingIds[1]);
  });
});