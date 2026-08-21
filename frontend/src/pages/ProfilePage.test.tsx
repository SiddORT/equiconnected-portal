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

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

function renderProfile() {
  return render(<MemoryRouter><ProfilePage /></MemoryRouter>);
}

describe('ProfilePage', () => {
  it('shows only the sections enabled by relational member roles', async () => {
    vi.mocked(profileApi.getProfile).mockResolvedValue({
      ...baseProfile, roles: ['horse_owner', 'stable_manager'],
    });
    renderProfile();
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Stable profile' })).toBeTruthy());
    expect(screen.getByRole('heading', { name: 'Your horses' })).toBeTruthy();

    cleanup();
    vi.mocked(profileApi.getProfile).mockResolvedValue(baseProfile);
    renderProfile();
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Your horses' })).toBeTruthy());
    expect(screen.queryByRole('heading', { name: 'Stable profile' })).toBeNull();
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
});