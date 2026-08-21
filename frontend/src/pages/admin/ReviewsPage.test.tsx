import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, render, screen, waitFor } from '@testing-library/react';
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
    expect(screen.getByTestId('review-card-list')).toBeTruthy();
    expect(screen.queryByRole('table', { name: 'Provider reviews' })).toBeNull();
    expect(screen.getByText('Wonderful care')).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'Hide' }));
    await waitFor(() => expect(adminApi.setAdminReviewCommentVisibility).toHaveBeenCalledWith('review-1', false));
    expect(await screen.findByRole('button', { name: 'Restore' })).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'Hidden' }));
    await waitFor(() => expect(adminApi.listAdminReviews).toHaveBeenLastCalledWith(
      expect.objectContaining({ comment_visible: false })
    ));
  });

  it('shows complete administrator review details in responsive cards', async () => {
    const longComment = `A detailed review with line breaks.\n${'Helpful follow-up care. '.repeat(60)}`;
    vi.mocked(adminApi.listAdminReviews).mockResolvedValue({
      ...response,
      data: [{
        ...response.data[0],
        comment: longComment,
        comment_visible: false,
      }],
    });

    render(<MemoryRouter><ReviewsPage /></MemoryRouter>);

    const card = await screen.findByTestId('review-card');
    expect(card.textContent).toContain('Austin Equine Clinic');
    expect(card.textContent).toContain('Amina Rider');
    expect(card.textContent).toContain('amina@example.com');
    expect(card.textContent).toContain('★★★★★');
    expect(card.textContent).toContain('5/5');
    expect(card.textContent).toContain(longComment);
    expect(card.textContent).toContain('Submitted 2026-01-01T00:00:00Z');
    expect(card.textContent).toContain('Hidden');
    expect(screen.getByRole('button', { name: 'Restore' })).toBeTruthy();
  });

  it('provides explicit empty and retry states for the card list', async () => {
    vi.mocked(adminApi.listAdminReviews)
      .mockRejectedValueOnce(new Error('Network unavailable'))
      .mockResolvedValueOnce({ ...response, data: [], meta: { ...response.meta, total: 0, total_pages: 0 } });
    const user = userEvent.setup();
    render(<MemoryRouter><ReviewsPage /></MemoryRouter>);

    expect(await screen.findByText('Failed to load reviews')).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'Try again' }));
    expect(await screen.findByText('No reviews found')).toBeTruthy();
    expect(screen.getByText('Member reviews will appear here.')).toBeTruthy();
  });

  it('removes a hidden review from the visible filter and refreshes the page', async () => {
    vi.mocked(adminApi.listAdminReviews)
      .mockResolvedValueOnce(response)
      .mockResolvedValueOnce({ ...response, data: [], meta: { ...response.meta, total: 0, total_pages: 0 } });
    vi.mocked(adminApi.setAdminReviewCommentVisibility).mockResolvedValue({
      ...response.data[0],
      comment_visible: false,
    });
    const user = userEvent.setup();
    render(<MemoryRouter initialEntries={['/admin/reviews?comment_visible=visible']}><ReviewsPage /></MemoryRouter>);

    expect(await screen.findByRole('button', { name: 'Hide' })).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'Hide' }));

    expect(await screen.findByText('No reviews found')).toBeTruthy();
    expect(screen.queryByTestId('review-card')).toBeNull();
    expect(adminApi.listAdminReviews).toHaveBeenLastCalledWith(expect.objectContaining({ comment_visible: true }));
  });

  it('removes a restored review from the hidden filter and refreshes the page', async () => {
    const hiddenResponse = {
      ...response,
      data: [{ ...response.data[0], comment_visible: false }],
    };
    vi.mocked(adminApi.listAdminReviews)
      .mockResolvedValueOnce(hiddenResponse)
      .mockResolvedValueOnce({ ...hiddenResponse, data: [], meta: { ...hiddenResponse.meta, total: 0, total_pages: 0 } });
    vi.mocked(adminApi.setAdminReviewCommentVisibility).mockResolvedValue({
      ...hiddenResponse.data[0],
      comment_visible: true,
    });
    const user = userEvent.setup();
    render(<MemoryRouter initialEntries={['/admin/reviews?comment_visible=hidden']}><ReviewsPage /></MemoryRouter>);

    expect(await screen.findByRole('button', { name: 'Restore' })).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'Restore' }));

    expect(await screen.findByText('No reviews found')).toBeTruthy();
    expect(screen.queryByTestId('review-card')).toBeNull();
    expect(adminApi.listAdminReviews).toHaveBeenLastCalledWith(expect.objectContaining({ comment_visible: false }));
  });

  it('keeps a provider scope in review requests and lets administrators return to all reviews', async () => {
    vi.mocked(adminApi.listAdminReviews).mockResolvedValue(response);
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={['/admin/reviews?provider_id=123e4567-e89b-42d3-a456-426614174000']}>
        <ReviewsPage />
      </MemoryRouter>
    );

    expect(await screen.findByText(/Showing reviews for/)).toBeTruthy();
    await waitFor(() => expect(adminApi.listAdminReviews).toHaveBeenCalledWith(
      expect.objectContaining({ provider_id: '123e4567-e89b-42d3-a456-426614174000' })
    ));

    await user.click(screen.getByRole('button', { name: 'View all reviews' }));
    await waitFor(() => expect(adminApi.listAdminReviews).toHaveBeenLastCalledWith(
      expect.objectContaining({ provider_id: undefined })
    ));
  });

  it('normalizes malformed URL filters before loading reviews', async () => {
    vi.mocked(adminApi.listAdminReviews).mockResolvedValue(response);
    render(
      <MemoryRouter initialEntries={[
        '/admin/reviews?provider_id=not-a-uuid&comment_visible=unexpected&page=not-a-page&page_size=999',
      ]}>
        <ReviewsPage />
      </MemoryRouter>
    );

    await waitFor(() => expect(adminApi.listAdminReviews).toHaveBeenCalledWith({
      provider_id: undefined,
      comment_visible: undefined,
      page: 1,
      page_size: 25,
    }));
    expect(screen.queryByRole('button', { name: 'View all reviews' })).toBeNull();
  });

  it('does not let a slower scoped request overwrite a newer unscoped list', async () => {
    let resolveScoped!: (value: typeof response) => void;
    const scopedRequest = new Promise<typeof response>((resolve) => {
      resolveScoped = resolve;
    });
    const unscopedResponse = {
      ...response,
      data: [{ ...response.data[0], provider_name: 'All Reviews Clinic' }],
    };
    vi.mocked(adminApi.listAdminReviews).mockImplementation((params) => (
      params?.provider_id ? scopedRequest : Promise.resolve(unscopedResponse)
    ));
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={['/admin/reviews?provider_id=123e4567-e89b-42d3-a456-426614174000']}>
        <ReviewsPage />
      </MemoryRouter>
    );

    await waitFor(() => expect(adminApi.listAdminReviews).toHaveBeenCalledWith(
      expect.objectContaining({ provider_id: '123e4567-e89b-42d3-a456-426614174000' })
    ));
    await user.click(screen.getByRole('button', { name: 'View all reviews' }));
    expect(await screen.findByText('All Reviews Clinic')).toBeTruthy();

    await act(async () => {
      resolveScoped({
        ...response,
        data: [{ ...response.data[0], provider_name: 'Scoped Only Clinic' }],
      });
      await Promise.resolve();
    });

    expect(screen.getByText('All Reviews Clinic')).toBeTruthy();
    expect(screen.queryByText('Scoped Only Clinic')).toBeNull();
  });
});