import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, useLocation } from 'react-router-dom';
import * as providersApi from '@/api/providers';
import { ProviderAccountPage } from './ProviderAccountPage';
import type { ProviderPortalProfile } from '@/types';

const mockLogout = vi.hoisted(() => vi.fn());

vi.mock('@/api/providers', () => ({
  getProviderPortalProfile: vi.fn(),
  getProviderPortalSpecializations: vi.fn(),
  updateProviderPortalProfile: vi.fn(),
  discardProviderPortalProfileUpdate: vi.fn(),
}));
vi.mock('@/api/client', () => ({
  extractErrorMessage: () => 'Provider portal unavailable',
}));
vi.mock('@/app/AuthContext', () => ({
  useAuth: () => ({
    user: { full_name: 'Approved Provider' },
    logout: mockLogout,
  }),
}));
vi.mock('@/app/TimeSettingsContext', () => ({
  useTimeSettings: () => ({
    formatTimestamp: (value: string) => `formatted ${value}`,
  }),
}));

const portalProfile: ProviderPortalProfile = {
  id: 'provider-1',
  name: 'Austin Equine Clinic',
  description: 'Trusted care',
  email: 'clinic@example.com',
  phone: null,
  website: null,
  visit_stability: 'STABLE_VISIT',
  specializations: [],
  locations: [],
  photos: [],
  phones: [],
  emails: [],
  doctor_profile: null,
  doctor_fields_available: false,
  qualifications: [],
  average_rating: 4.5,
  review_count: 1,
  visible_reviews: [{
    id: 'visible-review',
    rating: 5,
    comment: 'Thoughtful and thorough care.',
    reviewer_name: 'Amina Rider',
    created_at: '2026-01-02T03:04:05Z',
  }],
  editable_profile: {
    name: 'Austin Equine Clinic',
    description: 'Trusted care',
    email: 'clinic@example.com',
    phone: null,
    website: null,
    visit_stability: 'STABLE_VISIT',
    specialization_ids: [],
    locations: [],
    phones: [],
    emails: [],
    photos: [],
    qualifications: [],
  },
  profile_update: null,
};

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

function LocationProbe() {
  const location = useLocation();
  return <output data-testid="location">{location.pathname}</output>;
}

describe('ProviderAccountPage', () => {
  it('renders the editable workspace instead of the legacy approved-account placeholder', async () => {
    vi.mocked(providersApi.getProviderPortalProfile).mockResolvedValue(portalProfile);
    vi.mocked(providersApi.getProviderPortalSpecializations).mockResolvedValue([]);

    render(<MemoryRouter><ProviderAccountPage /></MemoryRouter>);

    expect(await screen.findByRole('heading', { name: 'Your profile' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Member feedback' })).toBeTruthy();
    expect(screen.queryByText('Your provider account is approved.')).toBeNull();
    expect(screen.queryByText(/more account tools are ready/)).toBeNull();
  });

  it('shows only member-visible feedback as timestamped cards without reviewer emails or moderation controls', async () => {
    vi.mocked(providersApi.getProviderPortalProfile).mockResolvedValue({
      ...portalProfile,
      visible_reviews: [
        ...portalProfile.visible_reviews,
        {
          id: 'hidden-review',
          rating: 1,
          comment: 'This hidden comment must not be rendered.',
          reviewer_name: 'Private Reviewer',
          created_at: '2026-01-03T03:04:05Z',
          comment_visible: false,
          reviewer_email: 'private@example.com',
        } as never,
      ],
    });
    vi.mocked(providersApi.getProviderPortalSpecializations).mockResolvedValue([]);

    render(<MemoryRouter><ProviderAccountPage /></MemoryRouter>);

    const card = await screen.findByTestId('review-card');
    expect(card.textContent).toContain('Amina Rider');
    expect(card.textContent).toContain('★★★★★');
    expect(card.textContent).toContain('Thoughtful and thorough care.');
    expect(card.textContent).toContain('Submitted formatted 2026-01-02T03:04:05Z');
    expect(screen.queryByText('private@example.com')).toBeNull();
    expect(screen.queryByText('This hidden comment must not be rendered.')).toBeNull();
    expect(screen.queryByText('Private Reviewer')).toBeNull();
    expect(screen.queryByRole('button', { name: 'Hide' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Restore' })).toBeNull();
    expect(screen.queryByText('Visible')).toBeNull();
    expect(screen.queryByText('Hidden')).toBeNull();
  });

  it('welcomes the provider and returns to provider sign in after logout', async () => {
    vi.mocked(providersApi.getProviderPortalProfile).mockResolvedValue(portalProfile);
    vi.mocked(providersApi.getProviderPortalSpecializations).mockResolvedValue([]);

    render(
      <MemoryRouter initialEntries={['/provider/account']}>
        <ProviderAccountPage />
        <LocationProbe />
      </MemoryRouter>
    );

    expect(await screen.findByText('Welcome,')).toBeTruthy();
    expect(screen.getByText('Approved Provider')).toBeTruthy();
    await userEvent.click(screen.getByRole('button', { name: 'Logout' }));

    await waitFor(() => expect(mockLogout).toHaveBeenCalledOnce());
    expect(screen.getByTestId('location').textContent).toBe('/provider/login');
  });

  it('opens the feedback drawer, moves focus to close, and closes on Escape', async () => {
    vi.mocked(providersApi.getProviderPortalProfile).mockResolvedValue(portalProfile);
    vi.mocked(providersApi.getProviderPortalSpecializations).mockResolvedValue([]);
    const user = userEvent.setup();

    render(<MemoryRouter><ProviderAccountPage /></MemoryRouter>);

    const trigger = await screen.findByRole('button', { name: 'Member feedback' });
    const drawer = screen.getByTestId('feedback-drawer');
    expect(trigger.getAttribute('aria-expanded')).toBe('false');
    expect(drawer.hasAttribute('hidden')).toBe(true);

    await user.click(trigger);
    expect(trigger.getAttribute('aria-expanded')).toBe('true');
    expect(drawer.hasAttribute('hidden')).toBe(false);
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Close member feedback' }));
    expect(screen.getByText('Thoughtful and thorough care.')).toBeTruthy();

    await user.keyboard('{Escape}');
    expect(trigger.getAttribute('aria-expanded')).toBe('false');
    expect(drawer.hasAttribute('hidden')).toBe(true);
    expect(document.activeElement).toBe(trigger);

    await user.click(trigger);
    await user.click(screen.getByRole('button', { name: 'Close member feedback' }));
    expect(trigger.getAttribute('aria-expanded')).toBe('false');
    expect(drawer.hasAttribute('hidden')).toBe(true);
    expect(document.activeElement).toBe(trigger);
  });

  it('uses structured fields for profile collections instead of JSON payloads', async () => {
    vi.mocked(providersApi.getProviderPortalProfile).mockResolvedValue(portalProfile);
    vi.mocked(providersApi.getProviderPortalSpecializations).mockResolvedValue([]);
    vi.mocked(providersApi.updateProviderPortalProfile).mockResolvedValue(portalProfile);
    const user = userEvent.setup();

    render(<MemoryRouter><ProviderAccountPage /></MemoryRouter>);

    await screen.findByRole('heading', { name: 'Your profile' });
    expect(screen.queryByText(/JSON list/i)).toBeNull();
    await user.click(screen.getByRole('button', { name: 'Add location' }));
    await user.type(screen.getByLabelText('Address line 1'), '42 Riding Lane');
    await user.type(screen.getByLabelText('City'), 'Dubai');
    await user.click(screen.getByRole('button', { name: 'Add photo' }));
    await user.type(screen.getByLabelText('Image link'), 'https://example.com/clinic.jpg');
    const form = screen.getByRole('button', { name: 'Save profile' }).closest('form');
    if (!form) throw new Error('Provider profile form was not rendered.');
    fireEvent.submit(form);

    await waitFor(() => expect(providersApi.updateProviderPortalProfile).toHaveBeenCalledWith(
      expect.objectContaining({
        locations: [expect.objectContaining({ address_line_1: '42 Riding Lane', city: 'Dubai', is_primary: true })],
        photos: [expect.objectContaining({ storage_reference: 'https://example.com/clinic.jpg', is_thumbnail: true })],
      })
    ));
  });

  it('keeps profile submission working with the full-width workspace', async () => {
    vi.mocked(providersApi.getProviderPortalProfile).mockResolvedValue(portalProfile);
    vi.mocked(providersApi.getProviderPortalSpecializations).mockResolvedValue([]);
    vi.mocked(providersApi.updateProviderPortalProfile).mockResolvedValue(portalProfile);

    render(<MemoryRouter><ProviderAccountPage /></MemoryRouter>);

    await screen.findByRole('heading', { name: 'Your profile' });
    expect(screen.getByTestId('provider-workspace').className).toContain('workspace');
    await userEvent.click(screen.getByRole('button', { name: 'Save profile' }));

    await waitFor(() => expect(providersApi.updateProviderPortalProfile).toHaveBeenCalledOnce());
    expect(screen.getByText('Your unpublished provider profile has been saved.')).toBeTruthy();
  });
});