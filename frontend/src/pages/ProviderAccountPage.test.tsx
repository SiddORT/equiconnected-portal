import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import * as providersApi from '@/api/providers';
import { ProviderAccountPage } from './ProviderAccountPage';
import type { ProviderPortalProfile } from '@/types';

vi.mock('@/api/providers', () => ({
  getProviderPortalProfile: vi.fn(),
  getProviderPortalSpecializations: vi.fn(),
  updateProviderPortalProfile: vi.fn(),
}));
vi.mock('@/api/client', () => ({
  getApiErrorCode: () => 'provider_portal_unavailable',
  extractErrorMessage: () => 'Provider portal unavailable',
}));
vi.mock('@/app/AuthContext', () => ({
  useAuth: () => ({
    user: { full_name: 'Approved Provider' },
    logout: vi.fn(),
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

describe('ProviderAccountPage', () => {
  it('preserves the approved self-registered provider account view outside the invitation portal', async () => {
    vi.mocked(providersApi.getProviderPortalProfile).mockRejectedValue(new Error('not invitation-linked'));
    vi.mocked(providersApi.getProviderPortalSpecializations).mockResolvedValue([]);

    render(<MemoryRouter><ProviderAccountPage /></MemoryRouter>);

    expect(await screen.findByText('Your provider account is approved.')).toBeTruthy();
    expect(screen.getByText(/Your directory listing is staged/)).toBeTruthy();
    expect(screen.queryByText('Provider portal access is unavailable.')).toBeNull();
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
});