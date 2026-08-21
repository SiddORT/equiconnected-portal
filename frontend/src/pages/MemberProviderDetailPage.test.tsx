import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import * as providersApi from '@/api/providers';
import { MemberProviderDetailPage } from './MemberProviderDetailPage';

vi.mock('@/api/providers', () => ({
  getMemberProvider: vi.fn(),
  saveMemberProviderReview: vi.fn(),
}));
vi.mock('@/app/TimeSettingsContext', () => ({
  useTimeSettings: () => ({
    formatTimestamp: (value: string) => value,
  }),
}));

const detail = {
  id: 'provider-1', provider_type: 'CLINIC' as const, name: 'Austin Equine Clinic',
  description: 'Trusted care', thumbnail_url: null, thumbnail_alt_text: null, website: null, email: null, phone: null,
  visit_stability: 'STABLE_VISIT' as const,
  location: { city: 'Austin', state_province: 'Texas', country: 'United States' },
  average_rating: 4.5, review_count: 2, distance_km: null,
  visible_reviews: [],
  own_review: { id: 'review-1', rating: 4, comment: '', comment_visible: false, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z' },
};

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

describe('MemberProviderDetailPage', () => {
  it('shows a hidden-comment explanation and submits an updated member review', async () => {
    vi.mocked(providersApi.getMemberProvider).mockResolvedValue(detail);
    vi.mocked(providersApi.saveMemberProviderReview).mockResolvedValue({
      ...detail.own_review, rating: 5, comment: 'Excellent follow-up', comment_visible: false,
    });
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={['/providers/provider-1']}>
        <Routes><Route path="/providers/:id" element={<MemberProviderDetailPage />} /></Routes>
      </MemoryRouter>
    );
    expect(await screen.findByText(/prior comment is currently hidden/i)).toBeTruthy();
    await user.selectOptions(screen.getByLabelText('Rating'), '5');
    await user.type(screen.getByLabelText('Comment (optional)'), 'Excellent follow-up');
    await user.click(screen.getByRole('button', { name: 'Save review' }));
    await waitFor(() => expect(providersApi.saveMemberProviderReview).toHaveBeenCalledWith(
      'provider-1', { rating: 5, comment: 'Excellent follow-up' }
    ));
    expect(await screen.findByText('Your review has been saved.')).toBeTruthy();
  });
});