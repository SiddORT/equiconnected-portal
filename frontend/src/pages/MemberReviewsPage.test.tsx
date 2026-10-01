import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { MemberReviewsPage } from './MemberReviewsPage';

const apiMocks = vi.hoisted(() => ({
  listMemberFeedback: vi.fn(),
  listMemberReviews: vi.fn(),
  getMemberFeedbackCounts: vi.fn(),
  getMemberReviewCounts: vi.fn(),
  updateMemberFeedback: vi.fn(),
  updateMemberReview: vi.fn(),
  withdrawMemberFeedback: vi.fn(),
  deleteMemberReview: vi.fn(),
}));
vi.mock('@/api/memberFeedback', () => apiMocks);
vi.mock('@/app/TimeSettingsContext', () => ({
  useTimeSettings: () => ({ formatTimestamp: (value: string) => `portal time ${value}` }),
}));

const page = <T,>(items: T[], total = items.length) => ({
  data: items,
  meta: { page: 1, page_size: 6, total, total_pages: 1 },
});

afterEach(() => { cleanup(); vi.resetAllMocks(); });

describe('MemberReviewsPage', () => {
  it('shows real review status, configured timestamps, and blocks edits to hidden reviews', async () => {
    apiMocks.listMemberReviews.mockResolvedValue(page([{
      id: 'r1', provider_id: 'p1', provider_name: 'Willowbank Equine', rating: 4,
      comment: 'A thoughtful visit.', status: 'HIDDEN', member_note: 'The comment is private.',
      created_at: '2026-04-01T10:00:00Z', updated_at: '2026-04-02T10:00:00Z', version: 2,
    }]));
    apiMocks.listMemberFeedback.mockResolvedValue(page([]));
    apiMocks.getMemberReviewCounts.mockResolvedValue({ hidden: 1, all: 1 });
    apiMocks.getMemberFeedbackCounts.mockResolvedValue({ total: 0 });
    render(<MemoryRouter><MemberReviewsPage /></MemoryRouter>);

    expect(await screen.findByText('Willowbank Equine')).toBeTruthy();
    expect(screen.getByText('Hidden')).toBeTruthy();
    expect(screen.getByText('The comment is private.')).toBeTruthy();
    expect(screen.getByText('Updated portal time 2026-04-02T10:00:00Z')).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Edit review' })).toBeNull();
    expect(screen.getByRole('button', { name: 'Delete' })).toBeTruthy();
  });

  it('lets a member edit only pending system feedback and never renders internal notes', async () => {
    const user = userEvent.setup();
    apiMocks.listMemberReviews.mockResolvedValue(page([]));
    apiMocks.listMemberFeedback.mockResolvedValue(page([{
      id: 'f1', category: 'Suggestion', subject: 'A clearer search', rating: 5,
      message: 'The filters could be easier to discover.', status: 'Pending', member_response: null,
      submitted_at: '2026-04-03T10:00:00Z', updated_at: '2026-04-03T10:00:00Z',
      version: 1, withdrawn_at: null,
    }]));
    apiMocks.getMemberReviewCounts.mockResolvedValue({ all: 0 });
    apiMocks.getMemberFeedbackCounts.mockResolvedValue({ total: 1 });
    render(<MemoryRouter><MemberReviewsPage /></MemoryRouter>);

    await user.click(await screen.findByRole('tab', { name: /System feedback/ }));
    expect(await screen.findByText('A clearer search')).toBeTruthy();
    expect(screen.getByText('Pending')).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'Edit feedback' }));
    expect(screen.getByLabelText('Feedback')).toBeTruthy();
    const rating = screen.getByLabelText('Overall experience (optional)') as HTMLSelectElement;
    expect(rating.value).toBe('5');
    await user.selectOptions(rating, '');
    expect(screen.getByRole('button', { name: 'Save feedback' })).toBeTruthy();
    expect(screen.getByText('Your note is private and can be edited or withdrawn while it is pending.')).toBeTruthy();
    expect(screen.queryByText(/internal note/i)).toBeNull();
    await user.click(screen.getByRole('button', { name: 'Save feedback' }));
    await waitFor(() => expect(apiMocks.updateMemberFeedback).toHaveBeenCalledWith(
      'f1', 1, expect.objectContaining({ rating: null })
    ));
  });

  it('saves a changed optional feedback rating as a number', async () => {
    const user = userEvent.setup();
    apiMocks.listMemberReviews.mockResolvedValue(page([]));
    apiMocks.listMemberFeedback.mockResolvedValue(page([{
      id: 'f2', category: 'Suggestion', subject: null, rating: null,
      message: 'A small idea.', status: 'Pending', member_response: null,
      submitted_at: '2026-04-03T10:00:00Z', updated_at: '2026-04-03T10:00:00Z',
      version: 1, withdrawn_at: null,
    }]));
    apiMocks.getMemberReviewCounts.mockResolvedValue({ all: 0 });
    apiMocks.getMemberFeedbackCounts.mockResolvedValue({ total: 1 });
    render(<MemoryRouter><MemberReviewsPage /></MemoryRouter>);

    await user.click(await screen.findByRole('tab', { name: /System feedback/ }));
    await screen.findByRole('heading', { name: 'Suggestion' });
    await user.click(screen.getByRole('button', { name: 'Edit feedback' }));
    await user.selectOptions(screen.getByLabelText('Overall experience (optional)'), '3');
    await user.click(screen.getByRole('button', { name: 'Save feedback' }));
    await waitFor(() => expect(apiMocks.updateMemberFeedback).toHaveBeenCalledWith(
      'f2', 1, expect.objectContaining({ rating: 3 })
    ));
  });

  it('shows an explicit retry state for failed member lists', async () => {
    apiMocks.listMemberReviews.mockRejectedValue(new Error('network unavailable'));
    apiMocks.listMemberFeedback.mockResolvedValue(page([]));
    apiMocks.getMemberReviewCounts.mockRejectedValue(new Error('network unavailable'));
    apiMocks.getMemberFeedbackCounts.mockResolvedValue({ total: 0 });
    render(<MemoryRouter><MemberReviewsPage /></MemoryRouter>);
    expect(await screen.findByText('We could not load this list')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Try again' })).toBeTruthy();
  });
});