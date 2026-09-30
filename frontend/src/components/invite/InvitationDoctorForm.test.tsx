import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { submitInvitation } from '@/api/invitations';
import type { InvitationTokenData } from '@/types';
import { InvitationDoctorForm } from './InvitationDoctorForm';

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

afterEach(cleanup);

it('submits the doctor invitation payload without organization associations', async () => {
  const user = userEvent.setup();
  render(
    <MemoryRouter initialEntries={['/invite']}>
      <Routes>
        <Route path="/invite" element={<InvitationDoctorForm token="public-invitation-token" data={data} />} />
        <Route path="/provider/invite/success" element={<p>Invitation complete</p>} />
      </Routes>
    </MemoryRouter>
  );

  expect(screen.queryByText(/organization association/i)).toBeNull();
  await user.click(screen.getByRole('button', { name: 'Submit for review' }));
  await waitFor(() => expect(submitInvitation).toHaveBeenCalled());
  expect(vi.mocked(submitInvitation).mock.calls[0][0]).toBe('public-invitation-token');
  const payload = vi.mocked(submitInvitation).mock.calls[0][1];
  expect(payload).not.toHaveProperty('organization_ids');
  expect(await screen.findByText('Invitation complete')).toBeTruthy();
});