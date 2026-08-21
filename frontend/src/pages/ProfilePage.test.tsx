import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import * as profileApi from '@/api/profile';
import { ProfilePage } from './ProfilePage';
import type { MemberProfile } from '@/types';

vi.mock('@/api/profile', () => ({
  getProfile: vi.fn(),
  lookupPostalCode: vi.fn(),
  savePersonal: vi.fn(),
  saveStable: vi.fn(),
  createHorse: vi.fn(),
  saveHorse: vi.fn(),
  deleteHorse: vi.fn(),
  uploadHorsePhoto: vi.fn(),
  removeHorsePhoto: vi.fn(),
}));

const baseProfile: MemberProfile = {
  first_name: 'Amina', last_name: 'Rider', email: 'amina@example.com',
  mobile_number: '+1 555 123 4567', address: null, country: 'United States',
  state_province: 'Texas', city: 'Austin', postal_code: null,
  roles: ['horse_owner'], stable_profile: null, horses: [],
};

const stableProfile = {
  id: 'stable-1',
  name: 'Oak Valley Stables',
  description: null,
  address: '14 Oak Lane',
  country: 'United States',
  state_province: 'Texas',
  city: 'Austin',
  postal_code: '78701',
  contact_name: 'Amina Rider',
  contact_phone: '+1 555 123 4567',
  contact_email: 'amina@example.com',
  updated_at: '',
};

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

function renderProfile(path = '/profile') {
  return render(<MemoryRouter initialEntries={[path]}><ProfilePage /></MemoryRouter>);
}

describe('ProfilePage', () => {
  it('shows only the sections enabled by relational member roles', async () => {
    vi.mocked(profileApi.getProfile).mockResolvedValue({
      ...baseProfile, roles: ['horse_owner', 'stable_manager'],
    });
    renderProfile();
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Stable Manager' })).toBeTruthy());
    expect(screen.getByRole('heading', { name: 'Horse Owner' })).toBeTruthy();

    cleanup();
    vi.mocked(profileApi.getProfile).mockResolvedValue(baseProfile);
    renderProfile();
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Horse Owner' })).toBeTruthy());
    expect(screen.queryByRole('heading', { name: 'Stable Manager' })).toBeNull();
  });

  it('validates horse name before creating a horse', async () => {
    const user = userEvent.setup();
    vi.mocked(profileApi.getProfile).mockResolvedValue(baseProfile);
    renderProfile();
    await user.click(await screen.findByRole('button', { name: 'Add horse' }));
    await user.clear(screen.getByLabelText('Horse name'));
    await user.click(screen.getByRole('button', { name: 'Save horse' }));
    expect(await screen.findByText('Horse name is required.')).toBeTruthy();
    expect(profileApi.createHorse).not.toHaveBeenCalled();
  });

  it('applies a postal lookup result while keeping the location picker available', async () => {
    vi.mocked(profileApi.getProfile).mockResolvedValue(baseProfile);
    vi.mocked(profileApi.lookupPostalCode).mockResolvedValue({
      status: 'match', city: 'Round Rock', state_province: 'Texas',
    });
    renderProfile();
    const postalCode = await screen.findByLabelText('Postal / ZIP code');
    fireEvent.change(postalCode, { target: { value: '78664' } });
    fireEvent.blur(postalCode);
    await waitFor(() => expect(profileApi.lookupPostalCode).toHaveBeenCalledWith('United States', '78664'));
    expect(screen.getByRole('button', { name: 'City' }).textContent).toContain('Round Rock');
  });

  it('shows role-aware section statuses and separates optional horse details', async () => {
    vi.mocked(profileApi.getProfile).mockResolvedValue({
      ...baseProfile,
      roles: ['horse_owner', 'stable_manager'],
    });
    renderProfile();

    expect(await screen.findByTestId('profile-progress-summary')).toBeTruthy();
    expect(screen.getByTestId('personal-section-status').textContent).toContain('2 items remaining');
    expect(screen.getByTestId('stable-section-status').textContent).toContain('8 items remaining');
    expect(screen.getByTestId('horses-section-status').textContent).toContain('1 item remaining');
    fireEvent.click(screen.getByRole('button', { name: 'Add horse' }));
    expect(screen.getByRole('heading', { name: 'Required basics' })).toBeTruthy();
    expect(screen.getByRole('heading', { name: 'Optional details' })).toBeTruthy();
  });

  it('focuses the requested guided section from the dashboard link', async () => {
    vi.mocked(profileApi.getProfile).mockResolvedValue(baseProfile);
    renderProfile('/profile?section=horses');

    const horsesHeading = await screen.findByRole('heading', { name: 'Horse Owner' });
    await waitFor(() => expect(document.activeElement).toBe(horsesHeading));
    expect(horsesHeading.closest('section')?.id).toBe('horses-profile-section');
  });

  it('keeps each save independent and preserves unsaved values in other sections', async () => {
    const user = userEvent.setup();
    const initial = { ...baseProfile, roles: ['horse_owner', 'stable_manager'], stable_profile: stableProfile };
    vi.mocked(profileApi.getProfile).mockResolvedValue(initial);
    vi.mocked(profileApi.savePersonal).mockResolvedValue({ ...initial, first_name: 'Updated' });
    vi.mocked(profileApi.saveStable).mockResolvedValue({ ...stableProfile, name: 'New Oak Valley' });
    renderProfile();

    await screen.findByRole('heading', { name: 'Stable Manager' });
    await user.clear(screen.getByLabelText('First name'));
    await user.type(screen.getByLabelText('First name'), 'Updated');
    await user.clear(screen.getByLabelText('Stable name'));
    await user.type(screen.getByLabelText('Stable name'), 'New Oak Valley');
    await user.click(screen.getByRole('button', { name: 'Save personal information' }));

    await waitFor(() => expect(profileApi.savePersonal).toHaveBeenCalledTimes(1));
    expect(profileApi.saveStable).not.toHaveBeenCalled();
    expect((screen.getByLabelText('Stable name') as HTMLInputElement).value).toBe('New Oak Valley');

    await user.clear(screen.getByLabelText('First name'));
    await user.type(screen.getByLabelText('First name'), 'Unsaved personal change');
    await user.click(screen.getByRole('button', { name: 'Save stable profile' }));

    await waitFor(() => expect(profileApi.saveStable).toHaveBeenCalledTimes(1));
    expect((screen.getByLabelText('First name') as HTMLInputElement).value).toBe('Unsaved personal change');
  });
});