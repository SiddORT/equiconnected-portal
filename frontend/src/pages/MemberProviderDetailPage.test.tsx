import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
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
  it('returns legacy landing-card links to the directory, including when details fail', async () => {
    vi.mocked(providersApi.getMemberProvider).mockResolvedValue(detail);
    const view = render(
      <MemoryRouter initialEntries={[{
        pathname: '/providers/provider-1', state: { fromCareNearYou: true },
      }]}>
        <Routes><Route path="/providers/:id" element={<MemberProviderDetailPage />} /></Routes>
      </MemoryRouter>
    );
    expect((await screen.findByRole('link', { name: '← Back to providers' })).getAttribute('href')).toBe('/providers');
    view.unmount();
    vi.mocked(providersApi.getMemberProvider).mockRejectedValue(new Error('Not found'));
    render(
      <MemoryRouter initialEntries={[{
        pathname: '/providers/provider-1', state: { fromCareNearYou: true },
      }]}>
        <Routes><Route path="/providers/:id" element={<MemberProviderDetailPage />} /></Routes>
      </MemoryRouter>
    );
    expect((await screen.findByRole('link', { name: 'Back to providers' })).getAttribute('href')).toBe('/providers');
  });
  it('preserves directory search and coordinates on normal back navigation', async () => {
    vi.mocked(providersApi.getMemberProvider).mockResolvedValue(detail);
    const user = userEvent.setup();
    function DirectoryReturn() {
      const location = useLocation();
      return <div>{location.search} / {JSON.stringify(location.state)}</div>;
    }
    render(
      <MemoryRouter initialEntries={[{
        pathname: '/providers/provider-1',
        search: '?type=CLINIC',
        state: { directoryCoordinates: { latitude: 30, longitude: -97 }, directoryLocationGranted: true },
      }]}>
        <Routes>
          <Route path="/providers/:id" element={<MemberProviderDetailPage />} />
          <Route path="/providers" element={<DirectoryReturn />} />
        </Routes>
      </MemoryRouter>
    );
    const back = await screen.findByRole('link', { name: '← Back to providers' });
    expect(back.getAttribute('href')).toBe('/providers?type=CLINIC');
    await user.click(back);
    expect(screen.getByText('?type=CLINIC / {"directoryCoordinates":{"latitude":30,"longitude":-97},"directoryLocationGranted":true}')).toBeTruthy();
  });
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

  it('renders visible member feedback as a full card with the submitted timestamp', async () => {
    vi.mocked(providersApi.getMemberProvider).mockResolvedValue({
      ...detail,
      visible_reviews: [{
        id: 'public-review',
        rating: 4,
        comment: `Excellent communication.\n${'A long but readable review. '.repeat(35)}`,
        reviewer_name: 'Maya Horse Owner',
        created_at: '2026-02-03T04:05:06Z',
      }],
    });

    render(
      <MemoryRouter initialEntries={['/providers/provider-1']}>
        <Routes><Route path="/providers/:id" element={<MemberProviderDetailPage />} /></Routes>
      </MemoryRouter>
    );

    const card = await screen.findByTestId('review-card');
    expect(card.textContent).toContain('Maya Horse Owner');
    expect(card.textContent).toContain('★★★★☆');
    expect(card.textContent).toContain('4/5');
    expect(card.textContent).toContain('Excellent communication.');
    expect(card.textContent).toContain('Submitted 2026-02-03T04:05:06Z');
  });
});