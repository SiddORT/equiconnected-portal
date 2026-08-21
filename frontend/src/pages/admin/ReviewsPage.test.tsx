import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import * as adminApi from '@/api/admin';
import { ReviewsPage } from './ReviewsPage';

vi.mock('@/api/admin', () => ({
  listAdminReviews: vi.fn(),
  setAdminReviewCommentVisibility: vi.fn(),
}));

vi.mock('@/app/TimeSettingsContext', () => ({
  useTimeSettings: () => ({
    settings: { timezone: 'UTC', date_format: 'month_day_year', time_format: '12_hour' },
    isLoading: false,
    error: null,
    formatTimestamp: (v: string) => v,
    formatDate: (v: string) => v,
    formatWeekday: (v: string) => v,
    refresh: vi.fn(),
  }),
}));

const response = {
  data: [{
    id: 'review-1', provider_id: 'provider-1', provider_name: 'Austin Equine Clinic',
    reviewer_id: 'member-1', reviewer_name: 'Amina Rider', reviewer_email: 'amina@example.com',
    rating: 5, comment: 'Wonderful care', comment_visible: true,
    created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
  }],
  meta: { page: 1, page_size: 25, total: 1, total_pages: 1 },
};

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

describe('ReviewsPage', () => {
  it('filters reviews by visibility and can hide a comment without removing the review', async () => {
    vi.mocked(adminApi.listAdminReviews).mockResolvedValue(response);
    vi.mocked(adminApi.setAdminReviewCommentVisibility).mockResolvedValue({
      ...response.data[0], comment_visible: false,
    });
    const user = userEvent.setup();
    render(<MemoryRouter><ReviewsPage /></MemoryRouter>);
    expect(await screen.findByText('Austin Equine Clinic')).toBeTruthy();
    expect(screen.getByRole('table', { name: 'Provider reviews' })).toBeTruthy();
    expect(screen.getByText('Wonderful care')).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'Hide' }));
    await waitFor(() => expect(adminApi.setAdminReviewCommentVisibility).toHaveBeenCalledWith('review-1', false));
    expect(await screen.findByRole('button', { name: 'Restore' })).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'Hidden' }));
    await waitFor(() => expect(adminApi.listAdminReviews).toHaveBeenLastCalledWith(
      expect.objectContaining({ comment_visible: false })
    ));
  });
});