import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import * as invitationsApi from '@/api/invitations';
import { CreateInvitationDialog } from './CreateInvitationDialog';

vi.mock('@/api/invitations', () => ({
  createInvitation: vi.fn(),
}));

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

describe('CreateInvitationDialog', () => {
  it('shows an existing-account error beside the recipient email', async () => {
    vi.mocked(invitationsApi.createInvitation).mockRejectedValue({
      isAxiosError: true,
      response: {
        data: {
          detail: {
            code: 'recipient_email_in_use',
            message: 'This email address already belongs to an EquiConnected account. Use a different email address to send a provider invitation.',
          },
        },
      },
    });
    const user = userEvent.setup();

    render(<CreateInvitationDialog onSuccess={vi.fn()} onCancel={vi.fn()} />);

    await user.type(screen.getByLabelText('Provider name'), 'Maple Equine Clinic');
    await user.type(screen.getByLabelText('Recipient email'), 'existing-account@example.com');
    await user.click(screen.getByRole('button', { name: 'Send invitation' }));

    expect(await screen.findByText(
      'This email address already belongs to an EquiConnected account. Use a different email address to send a provider invitation.',
    )).toBeTruthy();
  });
});