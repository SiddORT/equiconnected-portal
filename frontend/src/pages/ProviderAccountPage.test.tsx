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
  uploadProviderPortalPhoto: vi.fn(),
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
  vi.unstubAllGlobals();
  vi.resetAllMocks();
});

function LocationProbe() {
  const location = useLocation();
  return <output data-testid="location">{location.pathname}</output>;
}

async function enterTab(user: ReturnType<typeof userEvent.setup>, label: string) {
  await user.click(await screen.findByRole('tab', { name: label }));
}

describe('ProviderAccountPage', () => {
  it('hides general description for doctors and leaves it out of profile saves', async () => {
    const profile = {
      ...portalProfile,
      doctor_fields_available: true,
      editable_profile: {
        ...portalProfile.editable_profile,
        description: 'Historical doctor description',
        biography: 'Doctor biography',
      },
    };
    vi.mocked(providersApi.getProviderPortalProfile).mockResolvedValue(profile);
    vi.mocked(providersApi.getProviderPortalSpecializations).mockResolvedValue([]);
    vi.mocked(providersApi.updateProviderPortalProfile).mockResolvedValue(profile);
    render(<MemoryRouter><ProviderAccountPage /></MemoryRouter>);

    await enterTab(userEvent.setup(), 'Professional details');
    await screen.findByLabelText('Biography');
    expect(screen.queryByLabelText('Description')).toBeNull();
    await userEvent.click(screen.getByRole('button', { name: 'Save profile' }));
    await waitFor(() => expect(providersApi.updateProviderPortalProfile).toHaveBeenCalled());
    const body = vi.mocked(providersApi.updateProviderPortalProfile).mock.calls[0][0];
    expect(body).not.toHaveProperty('description');
    expect(body.biography).toBe('Doctor biography');
  });

  it.each(['Clinic', 'Hospital'])('keeps description editable for a %s profile', async (type) => {
    const profile = {
      ...portalProfile,
      name: `${type} profile`,
      editable_profile: { ...portalProfile.editable_profile, description: `${type} description` },
    };
    vi.mocked(providersApi.getProviderPortalProfile).mockResolvedValue(profile);
    vi.mocked(providersApi.getProviderPortalSpecializations).mockResolvedValue([]);
    vi.mocked(providersApi.updateProviderPortalProfile).mockResolvedValue(profile);
    render(<MemoryRouter><ProviderAccountPage /></MemoryRouter>);

    const description = await screen.findByLabelText('Description') as HTMLTextAreaElement;
    expect(description.value).toBe(`${type} description`);
    fireEvent.change(description, { target: { value: `Updated ${type} description` } });
    await userEvent.click(screen.getByRole('button', { name: 'Save profile' }));
    await waitFor(() => expect(providersApi.updateProviderPortalProfile).toHaveBeenCalledWith(
      expect.objectContaining({ description: `Updated ${type} description` })
    ));

    fireEvent.change(screen.getByLabelText('Description'), { target: { value: '' } });
    await userEvent.click(screen.getByRole('button', { name: 'Save profile' }));
    await waitFor(() => expect(providersApi.updateProviderPortalProfile).toHaveBeenLastCalledWith(
      expect.objectContaining({ description: null })
    ));
  });

  it.each(['CLINIC', 'HOSPITAL'] as const)(
    'prefills and saves zero years of experience from the %s editable profile',
    async () => {
      const profile = {
        ...portalProfile,
        editable_profile: {
          ...portalProfile.editable_profile,
          years_experience: 0,
        },
      };
      vi.mocked(providersApi.getProviderPortalProfile).mockResolvedValue(profile);
      vi.mocked(providersApi.getProviderPortalSpecializations).mockResolvedValue([]);
      vi.mocked(providersApi.updateProviderPortalProfile).mockResolvedValue(profile);

      render(<MemoryRouter><ProviderAccountPage /></MemoryRouter>);

      await enterTab(userEvent.setup(), 'Professional details');
      expect((await screen.findByLabelText('Years of experience') as HTMLInputElement).value).toBe('0');
      await userEvent.click(screen.getByRole('button', { name: 'Save profile' }));

      await waitFor(() => expect(providersApi.updateProviderPortalProfile).toHaveBeenCalledWith(
        expect.objectContaining({ years_experience: 0 })
      ));
    }
  );

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

    await enterTab(user, 'Contact & location');
    await screen.findByRole('heading', { name: 'Your profile' });
    expect(screen.queryByText(/JSON list/i)).toBeNull();
    await user.click(screen.getByRole('button', { name: 'Add location' }));
    await user.type(screen.getByLabelText('Address line 1'), '42 Riding Lane');
    await user.type(screen.getByLabelText('City'), 'Dubai');
    const form = screen.getByRole('button', { name: 'Save profile' }).closest('form');
    if (!form) throw new Error('Provider profile form was not rendered.');
    fireEvent.submit(form);

    await waitFor(() => expect(providersApi.updateProviderPortalProfile).toHaveBeenCalledWith(
      expect.objectContaining({
        locations: [expect.objectContaining({ address_line_1: '42 Riding Lane', city: 'Dubai', is_primary: true })],
      })
    ));
  });

  it.each([
    ['unpublished draft', 'direct'],
    ['published provider profile', 'pending'],
  ] as const)('uploads, explicitly saves, and reloads photos for %s', async (_label, saveState) => {
    vi.stubGlobal('URL', {
      createObjectURL: vi.fn(() => 'blob:provider-photo'),
      revokeObjectURL: vi.fn(),
    });
    const savedPhoto = {
      id: 'photo-1',
      provider_id: portalProfile.id,
      storage_reference: '/uploads/providers/provider-1/photos/clinic.png',
      alt_text: 'A horse clinic exterior',
      caption: 'Clinic entrance',
      display_order: 0,
      is_thumbnail: true,
      created_at: '2026-08-20T08:15:00Z',
      updated_at: '2026-08-20T08:15:00Z',
    };
    const savedProfile: ProviderPortalProfile = {
      ...portalProfile,
      photos: [savedPhoto],
      editable_profile: {
        ...portalProfile.editable_profile,
        photos: [{
          storage_reference: savedPhoto.storage_reference,
          alt_text: savedPhoto.alt_text,
          caption: savedPhoto.caption,
          display_order: savedPhoto.display_order,
          is_thumbnail: savedPhoto.is_thumbnail,
        }],
      },
      profile_update: saveState === 'pending' ? {
        id: 'profile-update-1',
        review_status: 'PENDING_REVIEW',
        submitted_at: '2026-08-20T08:15:00Z',
        reviewed_at: null,
        reviewed_by_name: null,
        rejection_reason: null,
      } : null,
    };
    vi.mocked(providersApi.getProviderPortalProfile)
      .mockResolvedValueOnce(portalProfile)
      .mockResolvedValueOnce(savedProfile);
    vi.mocked(providersApi.getProviderPortalSpecializations).mockResolvedValue([]);
    vi.mocked(providersApi.uploadProviderPortalPhoto).mockResolvedValue({
      storage_reference: savedPhoto.storage_reference,
      alt_text: savedPhoto.alt_text,
      caption: savedPhoto.caption,
      display_order: 0,
      is_thumbnail: false,
    });
    vi.mocked(providersApi.updateProviderPortalProfile).mockResolvedValue(savedProfile);
    const user = userEvent.setup();
    const view = render(<MemoryRouter><ProviderAccountPage /></MemoryRouter>);

    await enterTab(user, 'Photos');
    await screen.findByRole('heading', { name: 'Your profile' });
    const image = new File(['image content'], 'clinic.png', { type: 'image/png' });
    const fileInput = document.querySelector('input[type="file"]');
    if (!fileInput) throw new Error('Photo file input was not rendered.');
    await user.upload(fileInput as HTMLInputElement, image);
    await user.type(screen.getByLabelText('Alt text'), 'A horse clinic exterior');
    await user.type(screen.getByLabelText('Image title'), 'Clinic entrance');
    expect(screen.getByText(/only staged in this form/)).toBeTruthy();
    await enterTab(user, 'Basic details');
    await enterTab(user, 'Photos');
    expect((screen.getByLabelText('Alt text') as HTMLInputElement).value).toBe('A horse clinic exterior');
    await user.click(screen.getByRole('button', { name: 'Upload photo' }));

    await waitFor(() => expect(providersApi.uploadProviderPortalPhoto).toHaveBeenCalledWith(
      image,
      { alt_text: 'A horse clinic exterior', caption: 'Clinic entrance' }
    ));
    expect(providersApi.updateProviderPortalProfile).not.toHaveBeenCalled();
    expect(screen.getByText('Uploaded, not yet saved')).toBeTruthy();
    expect(screen.getByText(/Photo upload complete\. The photo is not part of your profile yet/)).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'Save profile' }));
    await waitFor(() => expect(providersApi.updateProviderPortalProfile).toHaveBeenCalledWith(
      expect.objectContaining({
        photos: [expect.objectContaining({
          storage_reference: savedPhoto.storage_reference,
          alt_text: 'A horse clinic exterior',
          caption: 'Clinic entrance',
          is_thumbnail: true,
        })],
      })
    ));
    expect(await screen.findByText(saveState === 'pending'
      ? /Your uploaded photos and profile changes were saved to a review request/
      : /Your uploaded photos and profile changes were saved to your unpublished provider profile/
    )).toBeTruthy();

    view.rerender(<MemoryRouter><ProviderAccountPage key="fresh-profile-load" /></MemoryRouter>);
    if (saveState === 'pending') {
      expect(await screen.findByText(/A profile update is awaiting review/)).toBeTruthy();
    } else {
      await screen.findByRole('heading', { name: 'Your profile' });
      expect(screen.queryByText(/A profile update is awaiting review/)).toBeNull();
    }
    await enterTab(user, 'Photos');
    expect((await screen.findByLabelText('Alt text') as HTMLInputElement).value).toBe('A horse clinic exterior');
    expect((screen.getByLabelText('Image title') as HTMLInputElement).value).toBe('Clinic entrance');
    expect(providersApi.getProviderPortalProfile).toHaveBeenCalledTimes(2);
    expect(screen.queryByText('Uploaded, not yet saved')).toBeNull();
  });

  it('blocks profile saves while a provider photo upload is still running', async () => {
    vi.stubGlobal('URL', {
      createObjectURL: vi.fn(() => 'blob:provider-photo'),
      revokeObjectURL: vi.fn(),
    });
    vi.mocked(providersApi.getProviderPortalProfile).mockResolvedValue(portalProfile);
    vi.mocked(providersApi.getProviderPortalSpecializations).mockResolvedValue([]);
    let finishUpload!: (photo: {
      storage_reference: string;
      alt_text: string | null;
      caption: string | null;
      display_order: number;
      is_thumbnail: boolean;
    }) => void;
    vi.mocked(providersApi.uploadProviderPortalPhoto).mockImplementation(() => new Promise((resolve) => {
      finishUpload = resolve;
    }));
    const user = userEvent.setup();

    render(<MemoryRouter><ProviderAccountPage /></MemoryRouter>);

    await enterTab(user, 'Photos');
    await screen.findByRole('heading', { name: 'Your profile' });
    const fileInput = document.querySelector('input[type="file"]');
    if (!fileInput) throw new Error('Photo file input was not rendered.');
    await user.upload(fileInput as HTMLInputElement, new File(['image content'], 'clinic.png', { type: 'image/png' }));
    await user.click(screen.getByRole('button', { name: 'Upload photo' }));

    const saveButton = screen.getByRole('button', { name: 'Save profile' });
    expect(saveButton.hasAttribute('disabled')).toBe(true);
    const form = saveButton.closest('form');
    if (!form) throw new Error('Provider profile form was not rendered.');
    fireEvent.submit(form);
    expect(providersApi.updateProviderPortalProfile).not.toHaveBeenCalled();
    expect(await screen.findByText(/Wait for photo uploads to finish before saving your profile/)).toBeTruthy();

    finishUpload({
      storage_reference: '/uploads/providers/provider-1/photos/clinic.png',
      alt_text: null,
      caption: null,
      display_order: 0,
      is_thumbnail: false,
    });
    expect(await screen.findByText('Uploaded, not yet saved')).toBeTruthy();
    expect(providersApi.updateProviderPortalProfile).not.toHaveBeenCalled();
  });

  it('opens the file picker from the browse photos drop zone', async () => {
    vi.mocked(providersApi.getProviderPortalProfile).mockResolvedValue(portalProfile);
    vi.mocked(providersApi.getProviderPortalSpecializations).mockResolvedValue([]);
    const user = userEvent.setup();

    render(<MemoryRouter><ProviderAccountPage /></MemoryRouter>);

    await enterTab(user, 'Photos');
    await screen.findByRole('heading', { name: 'Your profile' });
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    const clickSpy = vi.spyOn(fileInput, 'click');
    await user.click(screen.getByRole('button', { name: 'Browse photos' }));

    expect(clickSpy).toHaveBeenCalledOnce();
  });

  it('provides keyboard-accessible tabs without submitting and retains basic edits while switching panels', async () => {
    vi.mocked(providersApi.getProviderPortalProfile).mockResolvedValue(portalProfile);
    vi.mocked(providersApi.getProviderPortalSpecializations).mockResolvedValue([]);
    vi.mocked(providersApi.updateProviderPortalProfile).mockResolvedValue(portalProfile);
    const user = userEvent.setup();

    render(<MemoryRouter><ProviderAccountPage /></MemoryRouter>);

    const basicTab = await screen.findByRole('tab', { name: 'Basic details' });
    expect(screen.getAllByRole('tab')).toHaveLength(5);
    expect(basicTab.getAttribute('aria-selected')).toBe('true');
    await user.clear(screen.getByLabelText('Provider or practice name'));
    await user.type(screen.getByLabelText('Provider or practice name'), 'Updated Austin Clinic');
    await user.click(basicTab);
    await user.keyboard('{ArrowRight}');
    expect(screen.getByRole('tab', { name: 'Professional details' }).getAttribute('aria-selected')).toBe('true');
    expect(providersApi.updateProviderPortalProfile).not.toHaveBeenCalled();
    await user.keyboard('{End}');
    expect(screen.getByRole('tab', { name: 'Photos' }).getAttribute('aria-selected')).toBe('true');
    expect(document.activeElement).toBe(screen.getByRole('tab', { name: 'Photos' }));
    await user.click(screen.getByRole('button', { name: 'Save profile' }));

    await waitFor(() => expect(providersApi.updateProviderPortalProfile).toHaveBeenCalledWith(
      expect.objectContaining({ name: 'Updated Austin Clinic' })
    ));
  });

  it('prefills legacy scalar contacts while structured collection values take precedence', async () => {
    const profile = {
      ...portalProfile,
      email: 'legacy@example.com',
      phone: '+971 50 000 0000',
      editable_profile: {
        ...portalProfile.editable_profile,
        email: 'legacy@example.com',
        phone: '+971 50 000 0000',
        emails: [{ email: 'directory@example.com', is_primary: true }],
        phones: [{ country_code: '+44', number: '20 7946 0958', is_primary: true }],
      },
    };
    vi.mocked(providersApi.getProviderPortalProfile).mockResolvedValue(profile);
    vi.mocked(providersApi.getProviderPortalSpecializations).mockResolvedValue([]);
    const user = userEvent.setup();

    render(<MemoryRouter><ProviderAccountPage /></MemoryRouter>);

    await enterTab(user, 'Contact & location');
    expect((screen.getByLabelText('Email address 1') as HTMLInputElement).value).toBe('directory@example.com');
    expect(screen.queryByLabelText('Email address 2')).toBeNull();
    expect((screen.getByLabelText('Phone number 1') as HTMLInputElement).value).toBe('20 7946 0958');
    expect(screen.getByRole('button', { name: 'Country code: United Kingdom +44' })).toBeTruthy();
    expect(screen.queryByLabelText('Phone number 2')).toBeNull();
  });

  it('restores the country from a legacy scalar phone and keeps cleared collections empty after saving', async () => {
    const profile = {
      ...portalProfile,
      email: 'legacy@example.com',
      phone: '+971 50 123 4567',
      editable_profile: {
        ...portalProfile.editable_profile,
        email: 'legacy@example.com',
        phone: '+971 50 123 4567',
        emails: [],
        phones: [],
      },
    };
    const clearedProfile = {
      ...profile,
      email: null,
      phone: null,
      editable_profile: {
        ...profile.editable_profile,
        email: null,
        phone: null,
        emails: [],
        phones: [],
      },
    };
    vi.mocked(providersApi.getProviderPortalProfile).mockResolvedValue(profile);
    vi.mocked(providersApi.getProviderPortalSpecializations).mockResolvedValue([]);
    vi.mocked(providersApi.updateProviderPortalProfile).mockResolvedValue(clearedProfile);
    const user = userEvent.setup();

    render(<MemoryRouter><ProviderAccountPage /></MemoryRouter>);

    await enterTab(user, 'Contact & location');
    expect((screen.getByLabelText('Phone number 1') as HTMLInputElement).value).toBe('50 123 4567');
    expect(screen.getByRole('button', { name: 'Country code: United Arab Emirates +971' })).toBeTruthy();
    expect((screen.getByLabelText('Email address 1') as HTMLInputElement).value).toBe('legacy@example.com');
    await user.click(screen.getByRole('button', { name: 'Remove phone 1' }));
    await user.click(screen.getByRole('button', { name: 'Remove email 1' }));
    await user.click(screen.getByRole('button', { name: 'Save profile' }));

    await waitFor(() => expect(providersApi.updateProviderPortalProfile).toHaveBeenCalledWith(
      expect.objectContaining({ phones: [], emails: [], phone: null, email: null })
    ));
    expect(screen.queryByLabelText('Phone number 1')).toBeNull();
    expect(screen.queryByLabelText('Email address 1')).toBeNull();
  });

  it('loads and saves stable-visit and emergency services with the selected country code', async () => {
    const profile = {
      ...portalProfile,
      visit_stability: 'STABLE_VISIT' as const,
      maximum_working_radius_km: 25,
      emergency_services_available: true,
      emergency_contact_number: '+971 50 123 4567',
      editable_profile: {
        ...portalProfile.editable_profile,
        visit_stability: 'STABLE_VISIT' as const,
        maximum_working_radius_km: 25,
        emergency_services_available: true,
        emergency_contact_number: '+971 50 123 4567',
      },
    };
    vi.mocked(providersApi.getProviderPortalProfile).mockResolvedValue(profile);
    vi.mocked(providersApi.getProviderPortalSpecializations).mockResolvedValue([]);
    vi.mocked(providersApi.updateProviderPortalProfile).mockResolvedValue(profile);
    vi.stubGlobal('matchMedia', vi.fn(() => ({ matches: false })));
    const user = userEvent.setup();

    render(<MemoryRouter><ProviderAccountPage /></MemoryRouter>);

    await enterTab(user, 'Services');
    expect((screen.getByLabelText('Maximum working radius (km)') as HTMLInputElement).value).toBe('25');
    expect((screen.getByLabelText('Offers stable visits') as HTMLInputElement).checked).toBe(true);
    expect((screen.getByLabelText('Emergency services available') as HTMLInputElement).checked).toBe(true);
    expect((screen.getByLabelText('Emergency contact number') as HTMLInputElement).value).toBe('50 123 4567');
    await user.click(screen.getByRole('button', { name: 'Country code: United Arab Emirates +971' }));
    await user.type(screen.getByRole('textbox', { name: 'Search countries' }), 'United Kingdom');
    await user.click(screen.getByRole('option', { name: /United Kingdom/ }));
    await user.click(screen.getByRole('button', { name: 'Save profile' }));

    await waitFor(() => expect(providersApi.updateProviderPortalProfile).toHaveBeenCalledWith(
      expect.objectContaining({
        visit_stability: 'STABLE_VISIT',
        maximum_working_radius_km: 25,
        emergency_services_available: true,
        emergency_contact_number: '+44 50 123 4567',
      })
    ));
  });

  it('validates newly enabled stable visits on their tab but allows an unchanged legacy radius gap', async () => {
    const user = userEvent.setup();
    const nonStableProfile = {
      ...portalProfile,
      visit_stability: 'NOT_STABLE_VISIT' as const,
      editable_profile: {
        ...portalProfile.editable_profile,
        visit_stability: 'NOT_STABLE_VISIT' as const,
        maximum_working_radius_km: null,
      },
    };
    vi.mocked(providersApi.getProviderPortalProfile).mockResolvedValue(nonStableProfile);
    vi.mocked(providersApi.getProviderPortalSpecializations).mockResolvedValue([]);
    render(<MemoryRouter><ProviderAccountPage /></MemoryRouter>);

    await enterTab(user, 'Services');
    await user.click(screen.getByLabelText('Offers stable visits'));
    await user.click(screen.getByRole('button', { name: 'Save profile' }));
    expect(await screen.findByText('Enter a finite radius greater than 0 km.')).toBeTruthy();
    expect(screen.getByRole('tab', { name: 'Services' }).getAttribute('aria-selected')).toBe('true');
    expect(providersApi.updateProviderPortalProfile).not.toHaveBeenCalled();

    cleanup();
    const legacyProfile = {
      ...portalProfile,
      emergency_services_available: true,
      emergency_contact_number: null,
      editable_profile: {
        ...portalProfile.editable_profile,
        visit_stability: 'STABLE_VISIT' as const,
        maximum_working_radius_km: null,
        emergency_services_available: true,
        emergency_contact_number: null,
      },
    };
    vi.mocked(providersApi.getProviderPortalProfile).mockResolvedValue(legacyProfile);
    vi.mocked(providersApi.getProviderPortalSpecializations).mockResolvedValue([]);
    vi.mocked(providersApi.updateProviderPortalProfile).mockResolvedValue(legacyProfile);
    render(<MemoryRouter><ProviderAccountPage /></MemoryRouter>);
    await user.click(await screen.findByRole('button', { name: 'Save profile' }));

    await waitFor(() => expect(providersApi.updateProviderPortalProfile).toHaveBeenCalledWith(
      expect.objectContaining({
        visit_stability: 'STABLE_VISIT',
        maximum_working_radius_km: null,
        emergency_services_available: true,
        emergency_contact_number: null,
      })
    ));
  });

  it('validates changed services without blocking a separate unchanged historical service gap', async () => {
    const legacyProfile = {
      ...portalProfile,
      emergency_services_available: true,
      emergency_contact_number: null,
      editable_profile: {
        ...portalProfile.editable_profile,
        visit_stability: 'STABLE_VISIT' as const,
        maximum_working_radius_km: null,
        emergency_services_available: true,
        emergency_contact_number: null,
      },
    };
    vi.mocked(providersApi.getProviderPortalProfile).mockResolvedValue(legacyProfile);
    vi.mocked(providersApi.getProviderPortalSpecializations).mockResolvedValue([]);
    vi.mocked(providersApi.updateProviderPortalProfile).mockResolvedValue(legacyProfile);
    const user = userEvent.setup();

    render(<MemoryRouter><ProviderAccountPage /></MemoryRouter>);

    await enterTab(user, 'Services');
    await user.type(screen.getByLabelText('Maximum working radius (km)'), '10');
    await user.click(screen.getByRole('button', { name: 'Save profile' }));

    await waitFor(() => expect(providersApi.updateProviderPortalProfile).toHaveBeenCalledWith(
      expect.objectContaining({
        maximum_working_radius_km: 10,
        emergency_services_available: true,
        emergency_contact_number: null,
      })
    ));
  });

  it('selects and clears all available specializations without duplicate selections', async () => {
    const profile = {
      ...portalProfile,
      editable_profile: { ...portalProfile.editable_profile, specialization_ids: ['spec-one'] },
    };
    vi.mocked(providersApi.getProviderPortalProfile).mockResolvedValue(profile);
    vi.mocked(providersApi.getProviderPortalSpecializations).mockResolvedValue([
      { id: 'spec-one', name: 'Dentistry', is_active: true },
      { id: 'spec-two', name: 'Surgery', is_active: true },
      { id: 'spec-two', name: 'Surgery', is_active: true },
      { id: 'spec-inactive', name: 'Retired specialty', is_active: false },
    ]);
    vi.mocked(providersApi.updateProviderPortalProfile).mockResolvedValue(profile);
    const user = userEvent.setup();

    render(<MemoryRouter><ProviderAccountPage /></MemoryRouter>);

    await enterTab(user, 'Services');
    expect(screen.queryByLabelText('Retired specialty')).toBeNull();
    expect(screen.getAllByLabelText('Surgery')).toHaveLength(1);
    const selectAll = screen.getByRole('button', { name: 'Select all' });
    expect(selectAll.getAttribute('aria-pressed')).toBe('mixed');
    await user.click(selectAll);
    expect((screen.getByLabelText('Dentistry') as HTMLInputElement).checked).toBe(true);
    expect((screen.getByLabelText('Surgery') as HTMLInputElement).checked).toBe(true);
    expect(selectAll.getAttribute('aria-pressed')).toBe('true');
    expect(selectAll.hasAttribute('disabled')).toBe(true);
    expect(providersApi.updateProviderPortalProfile).not.toHaveBeenCalled();
    await user.click(screen.getByRole('button', { name: 'Clear all' }));
    expect((screen.getByLabelText('Dentistry') as HTMLInputElement).checked).toBe(false);
    expect(screen.getByRole('button', { name: 'Select all' }).hasAttribute('disabled')).toBe(false);
    await user.click(screen.getByRole('button', { name: 'Save profile' }));

    await waitFor(() => expect(providersApi.updateProviderPortalProfile).toHaveBeenCalledWith(
      expect.objectContaining({ specialization_ids: [] })
    ));
  });

  it('lets doctors edit and clear experience notes with the admin-compatible length limit', async () => {
    const profile = {
      ...portalProfile,
      doctor_fields_available: true,
      editable_profile: {
        ...portalProfile.editable_profile,
        experience_description: 'Existing experience notes',
      },
    };
    vi.mocked(providersApi.getProviderPortalProfile).mockResolvedValue(profile);
    vi.mocked(providersApi.getProviderPortalSpecializations).mockResolvedValue([]);
    vi.mocked(providersApi.updateProviderPortalProfile).mockResolvedValue(profile);
    const user = userEvent.setup();

    render(<MemoryRouter><ProviderAccountPage /></MemoryRouter>);

    await enterTab(user, 'Professional details');
    const notes = screen.getByLabelText('Experience notes') as HTMLTextAreaElement;
    expect(notes.value).toBe('Existing experience notes');
    expect(notes.maxLength).toBe(5000);
    await user.clear(notes);
    await user.click(screen.getByRole('button', { name: 'Save profile' }));

    await waitFor(() => expect(providersApi.updateProviderPortalProfile).toHaveBeenCalledWith(
      expect.objectContaining({ experience_description: null })
    ));
  });

  it('routes hidden native validation failures to the tab containing the invalid field', async () => {
    vi.mocked(providersApi.getProviderPortalProfile).mockResolvedValue(portalProfile);
    vi.mocked(providersApi.getProviderPortalSpecializations).mockResolvedValue([]);
    const user = userEvent.setup();

    render(<MemoryRouter><ProviderAccountPage /></MemoryRouter>);

    await enterTab(user, 'Contact & location');
    fireEvent.change(screen.getByLabelText('Email address 1'), { target: { value: 'not-an-email' } });
    await enterTab(user, 'Basic details');
    await user.click(screen.getByRole('button', { name: 'Save profile' }));

    await waitFor(() => expect(screen.getByRole('tab', { name: 'Contact & location' }).getAttribute('aria-selected')).toBe('true'));
    expect(document.activeElement).toBe(screen.getByLabelText('Email address 1'));
    expect(providersApi.updateProviderPortalProfile).not.toHaveBeenCalled();
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