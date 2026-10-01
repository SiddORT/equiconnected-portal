import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import type { ProviderRankingResponse } from '@/types/analytics';
import { ProviderRankingTable } from './ProviderRankingTable';

afterEach(cleanup);

const report: ProviderRankingResponse = {
  data: [{
    provider_id: 'provider-1',
    name: 'Northwind Stables',
    provider_type: 'Stable',
    provider_status: 'active',
    publication_status: 'published',
    profile_views: 143,
    profile_views_available: true,
    review_submissions: 7,
    average_rating: 4.6,
    rating_count: 23,
    saved_count: 12,
  }],
  meta: { page: 1, page_size: 10, total: 1, total_pages: 1 },
  period: { preset: 'last_30_days', date_from: null, date_to: null, group_by: 'daily' },
  timezone: 'UTC',
  coverage: { available: true },
};

function renderTable() {
  const onSort = vi.fn();
  const onSearch = vi.fn();
  render(<MemoryRouter><ProviderRankingTable report={report} loading={false} search="" onSearch={onSearch} sortBy="profile_views"
    sortDirection="desc" onSort={onSort} page={1} pageSize={10} onPage={vi.fn()} onPageSize={vi.fn()} /></MemoryRouter>);
  return { onSort, onSearch };
}

describe('ProviderRankingTable', () => {
  it('shows the four core columns and exposes secondary fields only on disclosure', async () => {
    renderTable();
    const table = screen.getByRole('table', { name: /Provider ranking/ });
    expect(table.querySelectorAll('thead th')).toHaveLength(4);
    expect(screen.getByRole('link', { name: 'Northwind Stables' })).toBeTruthy();
    expect(screen.getByText('143')).toBeTruthy();
    expect(screen.getByText('7')).toBeTruthy();
    expect(screen.getByText('4.6 / 5')).toBeTruthy();
    expect(screen.getByText('23 eligible')).toBeTruthy();
    expect(document.querySelector('th details')?.hasAttribute('open')).toBe(false);
    fireEvent.click(screen.getByText('Provider details'));
    await waitFor(() => expect(screen.getByText('Current saves')).toBeTruthy());
    expect(screen.getByRole('link', { name: 'View reviews' })).toBeTruthy();
  });

  it('reveals extra sortable snapshot fields on demand and retains search as the provider filter', async () => {
    const { onSort, onSearch } = renderTable();
    expect(screen.getByRole('textbox', { name: 'Search providers' })).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Eligible rating count' })).toBeNull();
    fireEvent.click(screen.getByText('Additional sort options'));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Eligible rating count' })).toBeTruthy());
    fireEvent.click(screen.getByRole('button', { name: 'Eligible rating count' }));
    expect(onSort).toHaveBeenCalledWith('rating_count');
    fireEvent.change(screen.getByRole('textbox', { name: 'Search providers' }), { target: { value: 'North' } });
    expect(onSearch).toHaveBeenCalledWith('North');
  });
});