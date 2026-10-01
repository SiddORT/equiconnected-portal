import { afterEach, expect, it, vi } from 'vitest';
import { StrictMode, useState } from 'react';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { lookupProviderPostalCode } from '@/api/auth';
import { saveInvitationDraft, submitInvitation } from '@/api/invitations';
import type { InvitationTokenData } from '@/types';
import { InvitationAddresses, emptyInvitationAddress, type InvitationAddress } from './InvitationProfileFields';
import { InvitationDoctorForm } from './InvitationDoctorForm';

vi.mock('@/api/auth', () => ({
  listProviderSignupLanguages: vi.fn().mockResolvedValue([]),
  lookupProviderPostalCode: vi.fn(),
}));

vi.mock('@/api/invitations', () => ({
  extractSubmitFieldErrors: vi.fn(() => ({})),
  getInvitationSpecializations: vi.fn().mockResolvedValue([]),
  saveInvitationDraft: vi.fn().mockResolvedValue(undefined),
  submitInvitation: vi.fn().mockResolvedValue(undefined),
}));

const data: InvitationTokenData = {
  id: 'invite-1',
  provider_type: 'DOCTOR',
  recipient_email: 'doctor@example.com',
  emails_edited: false,
  provider: {
    name: 'Dr. Avery Quinn',
    description: null,
    email: null,
    phone: null,
    website: null,
    visit_stability: 'NOT_STABLE_VISIT',
    status: 'ACTIVE',
    specialization_ids: [],
    locations: [],
    phones: [],
    emails: [],
    photos: [],
    professional_title: null,
    biography: null,
    years_experience: null,
    experience_description: null,
  },
};

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.mocked(lookupProviderPostalCode).mockReset();
});

function ControlledInvitationAddresses({ initial }: { initial: InvitationAddress[] }) {
  const [value, setValue] = useState(initial);
  return <InvitationAddresses value={value} onChange={setValue} />;
}

const postalMatch = {
  status: 'match' as const,
  candidates: [{
    postal_code: 'M5V 1E3',
    country: 'Canada',
    country_code: 'ca',
    state_province: 'ON',
    city: 'Toronto',
    display_name: 'Toronto, Ontario, Canada',
  }],
};

it('restores structured names and submits them without organization associations', async () => {
  const user = userEvent.setup();
  render(
    <MemoryRouter initialEntries={['/invite']}>
      <Routes>
        <Route path="/invite" element={<InvitationDoctorForm token="public-invitation-token" data={{ ...data, provider: { ...data.provider, first_name: 'Avery', last_name: 'Quinn' } }} />} />
        <Route path="/provider/invite/success" element={<p>Invitation complete</p>} />
      </Routes>
    </MemoryRouter>
  );

  expect(screen.queryByText(/organization association/i)).toBeNull();
  expect((screen.getByLabelText('First name') as HTMLInputElement).value).toBe('Avery');
  expect((screen.getByLabelText('Last name') as HTMLInputElement).value).toBe('Quinn');
  await user.click(screen.getByRole('button', { name: 'Submit for review' }));
  await waitFor(() => expect(submitInvitation).toHaveBeenCalled());
  expect(vi.mocked(submitInvitation).mock.calls[0][0]).toBe('public-invitation-token');
  const payload = vi.mocked(submitInvitation).mock.calls[0][1];
  expect(payload).not.toHaveProperty('organization_ids');
  expect(payload).toMatchObject({ name: 'Avery Quinn', first_name: 'Avery', last_name: 'Quinn' });
  expect(await screen.findByText('Invitation complete')).toBeTruthy();
});

it('keeps an older full name visible until the invitee enters both names, including after a draft reload', async () => {
  const user = userEvent.setup();
  const { unmount } = render(<MemoryRouter><InvitationDoctorForm token="token" data={data} /></MemoryRouter>);
  expect(screen.getByText(/Previously entered name: Dr. Avery Quinn/)).toBeTruthy();
  expect(screen.queryByLabelText('Full name')).toBeNull();
  await user.click(screen.getByRole('button', { name: 'Submit for review' }));
  expect(submitInvitation).not.toHaveBeenCalled();
  await user.type(screen.getByLabelText('First name'), 'Avery');
  await user.click(screen.getByRole('button', { name: 'Save draft' }));
  await waitFor(() => expect(saveInvitationDraft).toHaveBeenCalledWith('token',
    expect.objectContaining({ name: 'Dr. Avery Quinn', first_name: 'Avery', last_name: null })));
  unmount();
  render(<MemoryRouter><InvitationDoctorForm token="token" data={{ ...data, provider: { ...data.provider, first_name: 'Avery' } }} /></MemoryRouter>);
  expect((screen.getByLabelText('First name') as HTMLInputElement).value).toBe('Avery');
  await user.type(screen.getByLabelText('Last name'), 'Quinn');
  await user.click(screen.getByRole('button', { name: 'Save draft' }));
  await waitFor(() => expect(saveInvitationDraft).toHaveBeenLastCalledWith('token',
    expect.objectContaining({ name: 'Avery Quinn', first_name: 'Avery', last_name: 'Quinn' })));
});

it('does not look up postal codes restored from a saved invitation', async () => {
  const savedAddress = {
    ...emptyInvitationAddress('saved'),
    postal_code: '78701',
    country: 'United States',
    city: 'Austin',
  };
  render(<ControlledInvitationAddresses initial={[savedAddress]} />);

  await new Promise((resolve) => window.setTimeout(resolve, 650));
  expect(lookupProviderPostalCode).not.toHaveBeenCalled();
  expect((screen.getByLabelText('Postal / ZIP code') as HTMLInputElement).value).toBe('78701');
  expect((screen.getByLabelText('City') as HTMLInputElement).value).toBe('Austin');
});

it('retains the legacy saved-address choice and loads the selected address', async () => {
  const user = userEvent.setup();
  const mainAddress = {
    ...emptyInvitationAddress('main'),
    name: 'Main clinic',
    address_line_1: '1 Main Street',
    city: 'Austin',
    postal_code: '78701',
  };
  const secondaryAddress = {
    ...emptyInvitationAddress('secondary'),
    name: 'Second clinic',
    address_line_1: '2 Oak Street',
    city: 'Dallas',
    postal_code: '75201',
  };
  render(<ControlledInvitationAddresses initial={[mainAddress, secondaryAddress]} />);

  await user.click(screen.getByRole('button', { name: 'Keep Main clinic — 1 Main Street, Austin' }));
  expect((screen.getByLabelText('City') as HTMLInputElement).value).toBe('Austin');
  expect(screen.getByRole('button', { name: 'Keep Main clinic — 1 Main Street, Austin' }).getAttribute('aria-pressed')).toBe('true');
  expect(lookupProviderPostalCode).not.toHaveBeenCalled();
});

it('keeps lookups for other addresses alive when one address postal code changes', async () => {
  const first = emptyInvitationAddress('first');
  const second = emptyInvitationAddress('second');
  const onChange = vi.fn();
  const { rerender, unmount } = render(<InvitationAddresses value={[first, second]} onChange={onChange} />);
  vi.mocked(lookupProviderPostalCode).mockImplementation(() => new Promise(() => {}));

  rerender(<InvitationAddresses value={[
    { ...first, postal_code: '11111' },
    { ...second, postal_code: '22222' },
  ]} onChange={onChange} />);
  await waitFor(() => expect(lookupProviderPostalCode).toHaveBeenCalledTimes(2), { timeout: 2000 });
  const firstSignal = vi.mocked(lookupProviderPostalCode).mock.calls.find(([postal]) => postal === '11111')?.[1];
  const secondSignal = vi.mocked(lookupProviderPostalCode).mock.calls.find(([postal]) => postal === '22222')?.[1];
  expect(firstSignal?.aborted).toBe(false);
  expect(secondSignal?.aborted).toBe(false);

  rerender(<InvitationAddresses value={[
    { ...first, postal_code: '33333' },
    { ...second, postal_code: '22222' },
  ]} onChange={onChange} />);
  await waitFor(() => expect(lookupProviderPostalCode).toHaveBeenCalledTimes(3), { timeout: 2000 });
  expect(firstSignal?.aborted).toBe(true);
  expect(secondSignal?.aborted).toBe(false);

  const newFirstSignal = vi.mocked(lookupProviderPostalCode).mock.calls[2][1];
  rerender(<InvitationAddresses value={[{ ...first, postal_code: '33333' }]} onChange={onChange} />);
  expect(secondSignal?.aborted).toBe(true);
  unmount();
  expect(newFirstSignal?.aborted).toBe(true);
});

it('requires an explicit choice from ambiguous postal matches and normalizes its country', async () => {
  const user = userEvent.setup();
  vi.mocked(lookupProviderPostalCode).mockResolvedValue({
    ...postalMatch,
    candidates: [
      ...postalMatch.candidates,
      { ...postalMatch.candidates[0], city: 'Etobicoke', display_name: 'Etobicoke, Ontario, Canada' },
    ],
  });
  render(<ControlledInvitationAddresses initial={[emptyInvitationAddress()]} />);
  await user.type(screen.getByLabelText('Postal / ZIP code'), 'M5V1E3');

  const matchingPlace = await screen.findByRole('button', { name: 'Toronto, Ontario, Canada' });
  expect((screen.getByLabelText('City') as HTMLInputElement).value).toBe('');
  await user.click(matchingPlace);

  expect((screen.getByLabelText('Country') as HTMLInputElement).value).toBe('Canada');
  expect((screen.getByLabelText('State / province') as HTMLInputElement).value).toBe('ON');
  expect((screen.getByLabelText('City') as HTMLInputElement).value).toBe('Toronto');
});

it('still requires an explicit choice for a unique postal match', async () => {
  const user = userEvent.setup();
  vi.mocked(lookupProviderPostalCode).mockResolvedValue(postalMatch);
  render(<StrictMode><ControlledInvitationAddresses initial={[emptyInvitationAddress()]} /></StrictMode>);
  await user.type(screen.getByLabelText('Postal / ZIP code'), 'M5V1E3');

  const matchingPlace = await screen.findByRole('button', { name: 'Toronto, Ontario, Canada' });
  expect((screen.getByLabelText('City') as HTMLInputElement).value).toBe('');
  await user.click(matchingPlace);
  expect((screen.getByLabelText('City') as HTMLInputElement).value).toBe('Toronto');
  await new Promise((resolve) => window.setTimeout(resolve, 650));
  expect(lookupProviderPostalCode).toHaveBeenCalledTimes(1);
});

it('cancels a pending lookup when location details are edited and suppresses its late result', async () => {
  const user = userEvent.setup();
  let signal: AbortSignal | undefined;
  let resolveLookup: ((result: Awaited<ReturnType<typeof lookupProviderPostalCode>>) => void) | undefined;
  vi.mocked(lookupProviderPostalCode).mockImplementation((_postalCode, requestSignal) => {
    signal = requestSignal;
    return new Promise<Awaited<ReturnType<typeof lookupProviderPostalCode>>>((resolve) => {
      resolveLookup = resolve;
    });
  });
  render(<ControlledInvitationAddresses initial={[emptyInvitationAddress()]} />);
  await user.type(screen.getByLabelText('Postal / ZIP code'), 'M5V1E3');
  await waitFor(() => expect(lookupProviderPostalCode).toHaveBeenCalled(), { timeout: 2000 });

  await user.type(screen.getByLabelText('City'), 'Manual City');
  expect(signal?.aborted).toBe(true);
  resolveLookup?.(postalMatch);
  await waitFor(() => expect((screen.getByLabelText('City') as HTMLInputElement).value).toBe('Manual City'));
  expect(screen.queryByRole('button', { name: 'Toronto, Ontario, Canada' })).toBeNull();
  expect(screen.queryByText('Choose a matching place or enter the address manually.')).toBeNull();
});

it('shows the shared unavailable message when the postal lookup fails', async () => {
  const user = userEvent.setup();
  vi.mocked(lookupProviderPostalCode).mockRejectedValue(new Error('lookup failed'));
  render(<ControlledInvitationAddresses initial={[emptyInvitationAddress()]} />);
  await user.type(screen.getByLabelText('Postal / ZIP code'), 'M5V1E3');

  expect(await screen.findByText('Postal lookup is unavailable. You can enter the address manually.')).toBeTruthy();
});
