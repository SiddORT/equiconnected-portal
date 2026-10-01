// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { StrictMode } from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import * as providersApi from '@/api/providers';
import * as messagesApi from '@/api/messages';
import { recordMemberTrafficView } from '@/analytics/trafficTracking';
import { MemberProviderDetailPage } from './MemberProviderDetailPage';

const { recordTrafficView } = vi.hoisted(() => ({
  recordTrafficView: vi.fn(),
}));

vi.mock('@/analytics/trafficTracking', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/analytics/trafficTracking')>()),
  recordMemberTrafficView: recordTrafficView,
}));

vi.mock('@/api/providers', () => ({
  getMemberProvider: vi.fn(),
  saveMemberProviderReview: vi.fn(),
  saveMemberProvider: vi.fn(),
  removeSavedMemberProvider: vi.fn(),
}));
vi.mock('@/api/messages', () => ({ getMessageAvailability: vi.fn() }));
vi.mock('@/app/TimeSettingsContext', () => ({
  useTimeSettings: () => ({
    formatTimestamp: (value: string) => value,
  }),
}));
vi.mock('@/api/memberHistoryRecording', () => ({ recordMemberHistory: vi.fn().mockResolvedValue(undefined) }));

const detail = {
  id: 'provider-1', is_saved: false, provider_type: 'CLINIC' as const, name: 'Austin Equine Clinic',
  description: 'Trusted care', thumbnail_url: null, thumbnail_alt_text: null, website: null, email: null, phone: null,
  visit_stability: 'STABLE_VISIT' as const,
  location: { city: 'Austin', state_province: 'Texas', country: 'United States' },
  average_rating: 4.5, review_count: 2, distance_km: null,
  visible_reviews: [],
  own_review: { id: 'review-1', rating: 4, comment: '', comment_visible: false, status: 'PENDING' as const, version: 1, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z' },
};

function renderProfile(entry: string | { pathname: string; search?: string; hash?: string; state?: unknown } = '/providers/provider-1') {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <Routes><Route path="/providers/:id" element={<MemberProviderDetailPage />} /></Routes>
    </MemoryRouter>
  );
}

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

beforeEach(() => {
  vi.mocked(messagesApi.getMessageAvailability).mockResolvedValue({
    available: false,
    reason: 'provider_account_unavailable',
    provider_name: 'Austin Equine Clinic',
  });
});

describe('MemberProviderDetailPage', () => {
  it('offers private messaging only when the server says it is available', async () => {
    vi.mocked(providersApi.getMemberProvider).mockResolvedValue(detail);
    vi.mocked(messagesApi.getMessageAvailability).mockResolvedValue({
      available: true,
      reason: null,
      provider_name: detail.name,
    });

    renderProfile();

    const messageLink = await screen.findByRole('link', { name: 'Message provider' });
    expect(messageLink.getAttribute('href')).toBe('/member/messages?provider_id=provider-1');
    expect(screen.getByRole('link', { name: /Contact provider/ })).toBeTruthy();
  });

  it('explains unavailable messaging while keeping direct contact actions in place', async () => {
    vi.mocked(providersApi.getMemberProvider).mockResolvedValue(detail);
    vi.mocked(messagesApi.getMessageAvailability).mockResolvedValue({
      available: false,
      reason: 'provider_account_unavailable',
      provider_name: detail.name,
    });

    renderProfile();

    expect(await screen.findByText('This provider does not currently have an active messaging account.')).toBeTruthy();
    expect(screen.getByRole('link', { name: /Contact provider/ })).toBeTruthy();
    expect(screen.queryByRole('link', { name: 'Message provider' })).toBeNull();
  });

  it('records one profile view when Strict Mode replays and races successful loads', async () => {
    const pending: Array<
      (value: Awaited<ReturnType<typeof providersApi.getMemberProvider>>) => void
    > = [];
    vi.mocked(providersApi.getMemberProvider).mockImplementation(
      () => new Promise((resolve) => pending.push(resolve)),
    );
    render(
      <StrictMode>
        <MemoryRouter initialEntries={['/providers/provider-1']}>
          <Routes><Route path="/providers/:id" element={<MemberProviderDetailPage />} /></Routes>
        </MemoryRouter>
      </StrictMode>,
    );

    await waitFor(() => expect(pending).toHaveLength(2));
    await act(async () => {
      pending.forEach((resolve) => resolve(detail));
    });

    expect(await screen.findByRole('heading', { name: 'Austin Equine Clinic' })).toBeTruthy();
    await waitFor(() => expect(recordMemberTrafficView).toHaveBeenCalledTimes(1));
    expect(recordMemberTrafficView).toHaveBeenCalledWith('provider_profile', 'provider-1');
  });

  it('shows the provider profile, preserves zero years, and uses ordered, persisted doctor details', async () => {
    vi.mocked(providersApi.getMemberProvider).mockResolvedValue({
      ...detail,
      provider_type: 'DOCTOR',
      professional_title: 'Equine veterinarian',
      biography: 'Thoughtful care for horses.',
      years_experience: 0,
      photos: [
        { url: '/first.jpg', alt_text: 'Horse at a clinic', caption: 'Clinic care', display_order: 0 },
        { url: '/second.jpg', alt_text: 'A second horse', caption: 'Follow-up visit', display_order: 1 },
      ],
      qualifications: [
        { title: 'Advanced Equine Medicine', institution: 'Texas A&M', year_obtained: 2024, description: null, display_order: 2 },
        { title: 'Doctor of Veterinary Medicine', institution: 'State University', year_obtained: 2018, description: 'Veterinary degree', display_order: 1 },
      ],
      specializations: ['Dentistry', 'Sports medicine'],
      languages: [{ name: 'English', code: 'en' }, { name: 'Spanish', code: 'es' }],
      locations: [
        { city: 'Austin', state_province: 'Texas', country: 'United States' },
        { city: 'Round Rock', state_province: 'Texas', country: 'United States' },
      ],
      maximum_working_radius_km: 50,
      clinic_hospital_visit: false,
      emergency_services_available: true,
      doctor_availability: 'VISITING',
      doctor_visits: [{
        start_date: '2026-04-01',
        end_date: '2026-04-03',
        location: { city: 'Austin', state_province: 'Texas', country: 'United States' },
      }],
    });

    renderProfile();

    expect(await screen.findByRole('heading', { name: 'Austin Equine Clinic' })).toBeTruthy();
    expect(screen.getByText('Equine veterinarian')).toBeTruthy();
    expect(screen.getAllByText('0 years').length).toBeGreaterThan(0);
    expect(screen.getByText('Thoughtful care for horses.')).toBeTruthy();
    const qualifications = screen.getByRole('heading', { name: 'Qualifications & experience' }).closest('section');
    expect(qualifications?.textContent?.indexOf('Doctor of Veterinary Medicine')).toBeLessThan(
      qualifications?.textContent?.indexOf('Advanced Equine Medicine') ?? -1
    );
    expect(screen.getByText('Dentistry')).toBeTruthy();
    expect(screen.getByText('Spanish')).toBeTruthy();
    expect(screen.getByText('Round Rock, Texas, United States')).toBeTruthy();
    expect(screen.getByText('Visiting')).toBeTruthy();
    expect(screen.getByText('Apr 1, 2026')).toBeTruthy();
    expect(screen.getByText(/contact the provider to confirm availability and response/i)).toBeTruthy();
    const hero = screen.getAllByRole('img', { name: 'Horse at a clinic' })[0];
    expect(hero.getAttribute('src')).toBe('/first.jpg');
    const galleryPhotos = screen.getAllByRole('img').filter(image => image.getAttribute('src')?.endsWith('.jpg'));
    expect(galleryPhotos.map(image => image.getAttribute('src'))).toEqual([
      '/first.jpg', '/first.jpg', '/second.jpg',
    ]);
  });

  it('saves and removes the provider on its profile', async () => {
    vi.mocked(providersApi.getMemberProvider).mockResolvedValue(detail);
    vi.mocked(providersApi.saveMemberProvider).mockResolvedValue();
    vi.mocked(providersApi.removeSavedMemberProvider).mockResolvedValue();
    const user = userEvent.setup();
    renderProfile();
    await user.click(await screen.findByRole('button', { name: 'Save Austin Equine Clinic for later' }));
    expect(providersApi.saveMemberProvider).toHaveBeenCalledWith('provider-1');
    await user.click(screen.getByRole('button', { name: 'Remove Austin Equine Clinic from saved providers' }));
    expect(providersApi.removeSavedMemberProvider).toHaveBeenCalledWith('provider-1');
  });
  it('returns legacy landing-card links to the directory, including when details fail', async () => {
    vi.mocked(providersApi.getMemberProvider).mockResolvedValue(detail);
    const view = render(
      <MemoryRouter initialEntries={[{
        pathname: '/providers/provider-1', state: { fromCareNearYou: true },
      }]}>
        <Routes><Route path="/providers/:id" element={<MemberProviderDetailPage />} /></Routes>
      </MemoryRouter>
    );
    expect((await screen.findByRole('link', { name: 'Back to providers' })).getAttribute('href')).toBe('/providers');
    expect(recordMemberTrafficView).toHaveBeenCalledTimes(1);
    view.unmount();
    recordTrafficView.mockClear();
    vi.mocked(providersApi.getMemberProvider).mockRejectedValue(new Error('Not found'));
    render(
      <MemoryRouter initialEntries={[{
        pathname: '/providers/provider-1', state: { fromCareNearYou: true },
      }]}>
        <Routes><Route path="/providers/:id" element={<MemberProviderDetailPage />} /></Routes>
      </MemoryRouter>
    );
    expect((await screen.findByRole('link', { name: 'Back to providers' })).getAttribute('href')).toBe('/providers');
    expect(recordMemberTrafficView).not.toHaveBeenCalled();
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
    const back = await screen.findByRole('link', { name: 'Back to providers' });
    expect(back.getAttribute('href')).toBe('/providers?type=CLINIC');
    await user.click(back);
    expect(screen.getByText('?type=CLINIC / {"directoryCoordinates":{"latitude":30,"longitude":-97},"directoryLocationGranted":true}')).toBeTruthy();
  });
  it('explains moderation and submits an updated member review to pending', async () => {
    vi.mocked(providersApi.getMemberProvider).mockResolvedValue({
      ...detail,
      visible_reviews: [{
        id: 'public-review', rating: 5, comment: 'A published member comment.',
        reviewer_name: 'Maya Horse Owner', created_at: '2026-02-03T04:05:06Z',
      }],
      review_count: 17,
      average_rating: 4.8,
    });
    vi.mocked(providersApi.saveMemberProviderReview).mockResolvedValue({
      ...detail.own_review, rating: 5, comment: 'Excellent follow-up', comment_visible: false,
    });
    vi.mocked(providersApi.getMemberProvider)
      .mockResolvedValueOnce({
        ...detail,
        visible_reviews: [{
          id: 'public-review', rating: 5, comment: 'A published member comment.',
          reviewer_name: 'Maya Horse Owner', created_at: '2026-02-03T04:05:06Z',
        }],
        review_count: 17,
        average_rating: 4.8,
      })
      .mockResolvedValueOnce({
        ...detail,
        visible_reviews: [{
          id: 'public-review', rating: 5, comment: 'A published member comment.',
          reviewer_name: 'Maya Horse Owner', created_at: '2026-02-03T04:05:06Z',
        }],
        review_count: 18,
        average_rating: 4.9,
        own_review: { ...detail.own_review, rating: 5, comment: 'Excellent follow-up', comment_visible: false },
      });
    const user = userEvent.setup();
    renderProfile();
    expect((await screen.findAllByText(/new reviews and edits await publication/i)).length).toBeGreaterThan(0);
    expect((screen.getByRole('radio', { name: '4 stars' }) as HTMLInputElement).checked).toBe(true);
    expect(screen.getByText('17 member reviews')).toBeTruthy();
    expect(screen.queryByText(/no comment provided/i)).toBeNull();
    await user.click(screen.getByRole('radio', { name: '5 stars' }));
    await user.type(screen.getByLabelText('Comment (optional)'), 'Excellent follow-up');
    await user.click(screen.getByRole('button', { name: 'Update review' }));
    await waitFor(() => expect(providersApi.saveMemberProviderReview).toHaveBeenCalledWith(
      'provider-1', { rating: 5, comment: 'Excellent follow-up', expected_version: 1 }
    ));
    expect(await screen.findByText(/Your review has been saved and is awaiting publication/)).toBeTruthy();
    expect(await screen.findByText('18 member reviews')).toBeTruthy();
  });

  it('keeps hidden review text private to its owner without offering an edit', async () => {
    vi.mocked(providersApi.getMemberProvider).mockResolvedValue({
      ...detail, own_review: { ...detail.own_review, status: 'HIDDEN', version: 3, comment: 'Owner-only hidden text', member_note: 'Comment removed by moderator.' },
    });
    renderProfile();
    expect(await screen.findByText('Owner-only hidden text')).toBeTruthy();
    expect(screen.getByText('Comment removed by moderator.')).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Update review' })).toBeNull();
    expect(screen.queryByLabelText('Comment (optional)')).toBeNull();
    expect(providersApi.saveMemberProviderReview).not.toHaveBeenCalled();
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

    renderProfile();

    const card = await screen.findByTestId('review-card');
    expect(card.textContent).toContain('Maya Horse Owner');
    expect(card.textContent).toContain('★★★★☆');
    expect(card.textContent).toContain('4/5');
    expect(card.textContent).toContain('Excellent communication.');
    expect(card.textContent).toContain('Submitted 2026-02-03T04:05:06Z');
  });

  it.each([
    ['CLINIC', 'Equine clinic'],
    ['HOSPITAL', 'Equine hospital'],
    ['DOCTOR', 'Equine doctor'],
  ] as const)('renders a sparse %s profile without inventing data or availability', async (provider_type, label) => {
    vi.mocked(providersApi.getMemberProvider).mockResolvedValue({
      ...detail,
      provider_type,
      location: null,
      description: null,
      thumbnail_url: null,
      thumbnail_alt_text: null,
      years_experience: null,
      average_rating: null,
      review_count: 0,
      visible_reviews: [],
      own_review: null,
      photos: [],
      qualifications: [],
      languages: [],
      specializations: [],
      emergency_services_available: false,
      doctor_availability: null,
      doctor_visits: [],
    });

    renderProfile();

    expect((await screen.findAllByText(label)).length).toBeGreaterThan(0);
    expect(screen.getAllByText('Location details unavailable').length).toBeGreaterThan(0);
    expect(screen.getByText('Not recorded')).toBeTruthy();
    expect(screen.getByLabelText('No provider photo available')).toBeTruthy();
    expect(screen.queryByRole('heading', { name: 'Gallery' })).toBeNull();
    expect(screen.queryByText('Ongoing')).toBeNull();
    expect(screen.queryByText('Visiting')).toBeNull();
    expect(screen.queryByText(/emergency services/i)).toBeNull();
    expect(screen.getByText('No contact details have been published.')).toBeTruthy();
  });

  it('uses published contact data and rejects unsafe website schemes', async () => {
    vi.mocked(providersApi.getMemberProvider)
      .mockResolvedValueOnce({
        ...detail,
        email: 'care@example.org',
        phone: '+1 512 555 0100',
        website: 'https://provider.example.org/care',
      })
      .mockResolvedValueOnce({
      ...detail,
      email: 'care@example.org',
      phone: '+1 512 555 0100',
      website: 'javascript:alert(1)',
    });
    const view = renderProfile();

    expect((await screen.findByRole('link', { name: /\+1 512 555 0100/ })).getAttribute('href')).toBe('tel:+1 512 555 0100');
    expect(screen.getByRole('link', { name: /care@example.org/ }).getAttribute('href')).toBe('mailto:care@example.org');
    const website = screen.getByRole('link', { name: /Visit website/ });
    expect(website.getAttribute('href')).toBe('https://provider.example.org/care');
    expect(website.getAttribute('rel')).toContain('noopener');
    view.unmount();
    renderProfile();
    expect(screen.queryByRole('link', { name: /Visit website/ })).toBeNull();
  });

  it('opens the real photo gallery with keyboard focus containment and restores focus on Escape', async () => {
    vi.mocked(providersApi.getMemberProvider).mockResolvedValue({
      ...detail,
      photos: [
        { url: '/first.jpg', alt_text: 'First image', caption: 'First caption', display_order: 0 },
        { url: '/second.jpg', alt_text: 'Second image', caption: 'Second caption', display_order: 1 },
      ],
    });
    const user = userEvent.setup();
    renderProfile();

    const openSecond = await screen.findByRole('button', { name: 'Open photo 2: Second caption' });
    openSecond.focus();
    await user.keyboard('{Enter}');
    const dialog = await screen.findByRole('dialog', { name: 'Provider photo gallery' });
    expect((screen.getByRole('button', { name: 'Close photo gallery' }) as HTMLButtonElement).ownerDocument.activeElement)
      .toBe(screen.getByRole('button', { name: 'Close photo gallery' }));
    expect(within(dialog).getByRole('img', { name: 'Second image' }).getAttribute('src')).toBe('/second.jpg');

    const lastButton = screen.getByRole('button', { name: 'View photo 2' });
    lastButton.focus();
    await user.keyboard('{Tab}');
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Close photo gallery' }));
    await user.keyboard('{Shift>}{Tab}{/Shift}');
    expect(document.activeElement).toBe(lastButton);
    await user.keyboard('{Escape}');
    await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Provider photo gallery' })).toBeNull());
    expect(document.activeElement).toBe(openSecond);
  });

  it('uses the selected thumbnail in the hero without changing gallery display order', async () => {
    vi.mocked(providersApi.getMemberProvider).mockResolvedValue({
      ...detail,
      photos: [
        { url: '/first.jpg', alt_text: 'First photo', caption: null, display_order: 0 },
        { url: '/selected.jpg', alt_text: 'Selected profile photo', caption: null, display_order: 1, is_thumbnail: true },
      ],
    });
    renderProfile();
    const photos = await screen.findAllByRole('img', { name: 'Selected profile photo' });
    expect(photos[0].getAttribute('src')).toBe('/selected.jpg');
    expect(within(screen.getByRole('button', { name: 'Open photo 1' })).getByRole('img').getAttribute('src')).toBe('/first.jpg');
  });

  it('keeps the saved review when refreshing the profile after a successful save fails', async () => {
    vi.mocked(providersApi.getMemberProvider)
      .mockResolvedValueOnce({ ...detail, own_review: null })
      .mockRejectedValueOnce(new Error('Refresh unavailable'));
    vi.mocked(providersApi.saveMemberProviderReview).mockResolvedValue({
      id: 'review-new', rating: 3, comment: 'A new review', comment_visible: false,
      created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
    });
    const user = userEvent.setup();
    renderProfile();

    await user.click(await screen.findByRole('radio', { name: '3 stars' }));
    await user.type(screen.getByLabelText('Comment (optional)'), 'A new review');
    await user.click(screen.getByRole('button', { name: 'Submit review' }));

    expect(await screen.findByText(/your review was saved\. the displayed profile could not refresh/i)).toBeTruthy();
    expect(providersApi.saveMemberProviderReview).toHaveBeenCalledWith(
      'provider-1', { rating: 3, comment: 'A new review' }
    );
    expect(screen.getByRole('button', { name: 'Update review' })).toBeTruthy();
    expect((screen.getByLabelText('Comment (optional)') as HTMLTextAreaElement).value).toBe('A new review');
  });

  it('prefills an existing review after loading the provider profile again', async () => {
    vi.mocked(providersApi.getMemberProvider).mockResolvedValue({
      ...detail,
      own_review: {
        id: 'saved-review',
        rating: 2,
        comment: 'Saved before the page was reloaded.',
        comment_visible: true,
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-02T00:00:00Z',
      },
    });
    renderProfile();

    expect(await screen.findByRole('button', { name: 'Update review' })).toBeTruthy();
    expect((screen.getByRole('radio', { name: '2 stars' }) as HTMLInputElement).checked).toBe(true);
    expect((screen.getByLabelText('Comment (optional)') as HTMLTextAreaElement).value)
      .toBe('Saved before the page was reloaded.');
  });

  it('shows a save error and enforces the review character limit', async () => {
    vi.mocked(providersApi.getMemberProvider).mockResolvedValue({ ...detail, own_review: null });
    vi.mocked(providersApi.saveMemberProviderReview).mockRejectedValue(new Error('Review service unavailable'));
    const user = userEvent.setup();
    renderProfile();

    const comment = await screen.findByLabelText('Comment (optional)');
    fireEvent.change(comment, { target: { value: 'x'.repeat(2001) } });
    await user.click(screen.getByRole('button', { name: 'Submit review' }));
    expect(await screen.findByText('Comments must be 2,000 characters or fewer.')).toBeTruthy();
    expect(providersApi.saveMemberProviderReview).not.toHaveBeenCalled();

    fireEvent.change(comment, { target: { value: 'A valid comment' } });
    await user.click(screen.getByRole('button', { name: 'Submit review' }));
    expect(await screen.findByText('Your review could not be saved.')).toBeTruthy();
  });

  it('scrolls a contact deep link to the contact card', async () => {
    const scrollIntoView = vi.fn();
    Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', { configurable: true, value: scrollIntoView });
    vi.mocked(providersApi.getMemberProvider).mockResolvedValue(detail);

    renderProfile({ pathname: '/providers/provider-1', hash: '#contact' });

    await screen.findByRole('heading', { name: 'Contact' });
    await waitFor(() => expect(scrollIntoView).toHaveBeenCalled());
  });

  it('preserves favorite failure feedback without changing its pressed state', async () => {
    vi.mocked(providersApi.getMemberProvider).mockResolvedValue(detail);
    vi.mocked(providersApi.saveMemberProvider).mockRejectedValue(new Error('Could not save provider'));
    const user = userEvent.setup();
    renderProfile();

    const save = await screen.findByRole('button', { name: 'Save Austin Equine Clinic for later' });
    await user.click(save);
    expect(await screen.findByText('Could not update saved providers. Try again.')).toBeTruthy();
    expect(save.getAttribute('aria-pressed')).toBe('false');
  });
});