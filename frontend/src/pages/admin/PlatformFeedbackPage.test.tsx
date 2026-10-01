import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import * as feedbackApi from '@/api/adminFeedback';
import { PlatformFeedbackDetailPage, PlatformFeedbackPage } from './PlatformFeedbackPage';

vi.mock('@/api/adminFeedback', () => ({
  listAdminPlatformFeedback: vi.fn(),
  getAdminPlatformFeedback: vi.fn(),
  updateAdminPlatformFeedback: vi.fn(),
}));

vi.mock('@/app/TimeSettingsContext', () => ({
  useTimeSettings: () => ({
    formatTimestamp: (value: string) => `portal ${value}`,
  }),
}));

const feedback = {
  id: 'feedback-1',
  member_id: 'member-1',
  submitter_name: 'Amina Rider',
  submitter_email: 'amina@example.com',
  category: 'Technical Issue' as const,
  subject: 'Search is stuck',
  rating: 2,
  message: 'The filter stopped responding after I changed regions.',
  status: 'Pending' as const,
  withdrawn_at: null,
  member_response: null,
  internal_note: null,
  version: 1,
  submitted_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};
const page = {
  data: [feedback],
  meta: { page: 1, page_size: 25, total: 1, total_pages: 1 },
};
const detail = {
  ...feedback,
  history: [{
    id: 'action-1',
    actor_id: 'member-1',
    actor_name: 'Amina Rider',
    actor_email: 'amina@example.com',
    actor_type: 'member',
    action: 'member_submitted',
    from_status: null,
    to_status: 'Pending' as const,
    version: 1,
    content_snapshot: {
      category: 'Technical Issue',
      subject: 'Search is stuck',
      rating: 2,
      message: 'The filter stopped responding after I changed regions.',
      status: 'Pending',
      member_response: 'We are reviewing this report.',
      internal_note: 'Reproduced in the test environment.',
    },
    created_at: '2026-01-01T00:00:00Z',
  }],
};

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

describe('PlatformFeedbackPage', () => {
  it('shows private sender, category, rating, status, timestamps and searches using q', async () => {
    vi.mocked(feedbackApi.listAdminPlatformFeedback).mockResolvedValue(page);
    const user = userEvent.setup();
    render(<MemoryRouter><PlatformFeedbackPage /></MemoryRouter>);

    const feedbackRow = await screen.findByRole('row', { name: /Amina Rider/ });
    expect(within(feedbackRow).getByText('amina@example.com')).toBeTruthy();
    expect(within(feedbackRow).getByText('Technical Issue')).toBeTruthy();
    expect(within(feedbackRow).getByText('2/5 rating')).toBeTruthy();
    expect(within(feedbackRow).getByText('portal 2026-01-01T00:00:00Z')).toBeTruthy();

    await user.type(screen.getByRole('searchbox', { name: 'Search platform feedback' }), 'region');
    await waitFor(() => expect(feedbackApi.listAdminPlatformFeedback).toHaveBeenLastCalledWith(
      expect.objectContaining({ q: 'region', page: 1 }),
    ), { timeout: 1500 });
  });

  it('filters withdrawn submissions while retaining their withdrawn badge', async () => {
    vi.mocked(feedbackApi.listAdminPlatformFeedback).mockResolvedValue({
      ...page,
      data: [{ ...feedback, withdrawn_at: '2026-02-01T00:00:00Z' }],
    });
    const user = userEvent.setup();
    render(<MemoryRouter><PlatformFeedbackPage /></MemoryRouter>);

    expect(await screen.findByText('Withdrawn')).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'Withdrawn' }));
    await waitFor(() => expect(feedbackApi.listAdminPlatformFeedback).toHaveBeenLastCalledWith(
      expect.objectContaining({ status: 'withdrawn', page: 1 }),
    ));
  });

  it('shows action snapshots and keeps response and internal notes distinct', async () => {
    vi.mocked(feedbackApi.getAdminPlatformFeedback).mockResolvedValue(detail);
    vi.mocked(feedbackApi.updateAdminPlatformFeedback).mockResolvedValue({
      ...detail,
      status: 'In review',
      version: 2,
      member_response: 'Thank you, we are looking into this.',
      internal_note: 'Assigned to support.',
    });
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={['/admin/feedback/feedback-1']}>
        <Routes>
          <Route path="/admin/feedback/:id" element={<PlatformFeedbackDetailPage />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByText('Retained submission and moderation snapshot')).toBeTruthy();
    expect(screen.getByText(/Amina Rider · amina@example.com · member/)).toBeTruthy();
    await user.click(screen.getByText('Retained submission and moderation snapshot'));
    expect(screen.getAllByText('The filter stopped responding after I changed regions.').length).toBeGreaterThan(0);
    expect(screen.getByText('member response')).toBeTruthy();
    expect(screen.getByText('We are reviewing this report.')).toBeTruthy();
    expect(screen.getByText('internal note')).toBeTruthy();
    expect(screen.getByText('Reproduced in the test environment.')).toBeTruthy();
    await user.selectOptions(screen.getByLabelText('Status'), 'In review');
    await user.type(screen.getByLabelText('Member-visible response'), 'Thank you, we are looking into this.');
    await user.type(screen.getByLabelText('Internal administrator note'), 'Assigned to support.');
    await user.click(screen.getByRole('button', { name: 'Save processing update' }));

    await waitFor(() => expect(feedbackApi.updateAdminPlatformFeedback).toHaveBeenCalledWith('feedback-1', {
      expected_version: 1,
      status: 'In review',
      member_response: 'Thank you, we are looking into this.',
      internal_note: 'Assigned to support.',
    }));
    await waitFor(() => expect(screen.getAllByText('In review').length).toBeGreaterThan(0));
  });
});