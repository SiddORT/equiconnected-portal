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
  it('requires both doctor names and sends normalized names, while organizations keep provider name', async () => {
    vi.mocked(invitationsApi.createInvitation).mockResolvedValue({} as never);
    const user = userEvent.setup();
    render(<CreateInvitationDialog onSuccess={vi.fn()} onCancel={vi.fn()} />);
    await user.selectOptions(screen.getByLabelText('Provider type'), 'DOCTOR');
    expect(screen.queryByLabelText('Provider name')).toBeNull();
    await user.type(screen.getByLabelText('First name'), '  Maya  ');
    await user.type(screen.getByLabelText('Recipient email'), 'doctor@example.com');
    await user.click(screen.getByRole('button', { name: 'Send invitation' }));
    expect(invitationsApi.createInvitation).not.toHaveBeenCalled();
    expect(screen.getByText('Enter a last name.')).toBeTruthy();
    await user.type(screen.getByLabelText('Last name'), ' Singh ');
    await user.click(screen.getByRole('button', { name: 'Send invitation' }));
    expect(invitationsApi.createInvitation).toHaveBeenCalledWith({
      recipient_email: 'doctor@example.com', provider_type: 'DOCTOR',
      provider_name: 'Maya Singh', first_name: 'Maya', last_name: 'Singh',
    });
  });

  it('keeps the organization provider name input', async () => {
    vi.mocked(invitationsApi.createInvitation).mockResolvedValue({} as never);
    const user = userEvent.setup();
    render(<CreateInvitationDialog onSuccess={vi.fn()} onCancel={vi.fn()} />);
    await user.selectOptions(screen.getByLabelText('Provider type'), 'CLINIC');
    await user.type(screen.getByLabelText('Provider name'), ' Cedar Clinic ');
    await user.type(screen.getByLabelText('Recipient email'), 'clinic@example.com');
    await user.click(screen.getByRole('button', { name: 'Send invitation' }));
    expect(invitationsApi.createInvitation).toHaveBeenCalledWith({
      recipient_email: 'clinic@example.com', provider_type: 'CLINIC', provider_name: 'Cedar Clinic',
    });
  });
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