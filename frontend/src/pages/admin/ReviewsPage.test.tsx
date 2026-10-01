import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import * as reviewsApi from '@/api/reviews';
import { ReviewsPage } from './ReviewsPage';

vi.mock('@/api/reviews', () => ({
  listAdminReviews: vi.fn(),
  getAdminReview: vi.fn(),
  updateAdminReview: vi.fn(),
}));

vi.mock('@/app/TimeSettingsContext', () => ({
  useTimeSettings: () => ({
    formatTimestamp: (value: string) => `portal ${value}`,
  }),
}));

const review = {
  id: 'review-1',
  provider_id: 'provider-1',
  provider_name: 'Austin Equine Clinic',
  reviewer_id: 'member-1',
  reviewer_name: 'Amina Rider',
  reviewer_email: 'amina@example.com',
  rating: 5,
  comment: 'Wonderful care',
  comment_visible: true,
  status: 'PENDING' as const,
  member_note: null,
  internal_note: null,
  version: 1,
  deleted_at: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};
const page = {
  data: [review],
  meta: { page: 1, page_size: 25, total: 1, total_pages: 1 },
};
const detail = {
  ...review,
  history: [{
    id: 'action-1',
    actor_id: null,
    actor_name: 'Amina Rider',
    actor_email: 'amina@example.com',
    actor_type: 'member',
    action: 'member_submitted',
    from_status: null,
    to_status: 'PENDING' as const,
    version: 1,
    content_snapshot: {
      rating: 5,
      comment: 'Wonderful care',
      member_note: 'Thanks for sharing your feedback.',
      internal_note: 'Checked and approved.',
      status: 'PENDING',
    },
    created_at: '2026-01-01T00:00:00Z',
  }],
};

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

describe('ReviewsPage', () => {
  it('loads a paginated admin table and filters by publication status', async () => {
    vi.mocked(reviewsApi.listAdminReviews).mockResolvedValue(page);
    const user = userEvent.setup();
    render(<MemoryRouter><ReviewsPage /></MemoryRouter>);

    const reviewRow = await screen.findByRole('row', { name: /Austin Equine Clinic/ });
    expect(within(reviewRow).getByText('amina@example.com')).toBeTruthy();
    expect(within(reviewRow).getByText('Pending')).toBeTruthy();
    expect(screen.getByLabelText('Pagination')).toBeTruthy();

    await user.click(screen.getByRole('button', { name: 'Hidden' }));
    await waitFor(() => expect(reviewsApi.listAdminReviews).toHaveBeenLastCalledWith(
      expect.objectContaining({ status: 'HIDDEN', page: 1 }),
    ));
  });

  it('loads review history and saves moderation status with the expected version', async () => {
    vi.mocked(reviewsApi.listAdminReviews).mockResolvedValue(page);
    vi.mocked(reviewsApi.getAdminReview)
      .mockResolvedValueOnce(detail)
      .mockResolvedValueOnce({ ...detail, status: 'PUBLISHED', version: 2 });
    vi.mocked(reviewsApi.updateAdminReview).mockResolvedValue({
      ...detail,
      status: 'PUBLISHED',
      version: 2,
      comment_visible: true,
    });
    const user = userEvent.setup();
    render(<MemoryRouter><ReviewsPage /></MemoryRouter>);

    await user.click(await screen.findByRole('button', { name: 'View' }));
    expect(await screen.findByText('Retained review snapshot')).toBeTruthy();
    expect(screen.getByText(/Amina Rider · amina@example.com · member/)).toBeTruthy();
    await user.click(screen.getByText('Retained review snapshot'));
    expect(screen.getByText('member note')).toBeTruthy();
    expect(screen.getByText('Thanks for sharing your feedback.')).toBeTruthy();
    expect(screen.getByText('internal note')).toBeTruthy();
    expect(screen.getByText('Checked and approved.')).toBeTruthy();
    expect(screen.getAllByText('Wonderful care').length).toBeGreaterThan(0);
    await user.click(screen.getByRole('button', { name: 'Approve & publish' }));

    await waitFor(() => expect(reviewsApi.updateAdminReview).toHaveBeenCalledWith('review-1', {
      status: 'PUBLISHED',
      expected_version: 1,
      member_note: null,
      internal_note: null,
    }));
    await waitFor(() => expect(screen.getAllByText('Published').length).toBeGreaterThan(0));
  });

  it('shows retained deleted records without offering moderation actions', async () => {
    vi.mocked(reviewsApi.listAdminReviews).mockResolvedValue({
      ...page,
      data: [{ ...review, deleted_at: '2026-02-01T00:00:00Z' }],
    });
    vi.mocked(reviewsApi.getAdminReview).mockResolvedValue({
      ...detail,
      deleted_at: '2026-02-01T00:00:00Z',
    });
    const user = userEvent.setup();
    render(<MemoryRouter><ReviewsPage /></MemoryRouter>);

    expect(await screen.findByText('Deleted')).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'View' }));
    expect(await screen.findByText(/retained content and action history/)).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Approve & publish' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Save notes' })).toBeNull();
  });
});