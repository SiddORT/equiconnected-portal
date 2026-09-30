import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { saveInvitationDraft, submitInvitation } from '@/api/invitations';
import type { InvitationTokenData } from '@/types';
import { InvitationDoctorForm } from './InvitationDoctorForm';

vi.mock('@/api/auth', () => ({
  listProviderSignupLanguages: vi.fn().mockResolvedValue([]),
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

afterEach(() => { cleanup(); vi.clearAllMocks(); });

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