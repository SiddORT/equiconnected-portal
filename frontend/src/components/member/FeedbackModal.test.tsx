import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { useState } from 'react';
import userEvent from '@testing-library/user-event';
import { FeedbackModal } from './FeedbackModal';

const { submitPlatformFeedback } = vi.hoisted(() => ({ submitPlatformFeedback: vi.fn() }));
vi.mock('@/api/memberFeedback', () => ({ submitPlatformFeedback }));

afterEach(() => { cleanup(); vi.resetAllMocks(); });

describe('FeedbackModal', () => {
  it('preserves text and reuses the same idempotency key after a recoverable failure', async () => {
    const user = userEvent.setup();
    submitPlatformFeedback.mockRejectedValueOnce(new Error('connection interrupted')).mockResolvedValueOnce({ id: 'feedback-1' });
    render(<FeedbackModal open onClose={() => {}} />);

    await user.selectOptions(screen.getByLabelText(/What is this about/), 'Website / App');
    await user.type(screen.getByLabelText('Your feedback Required'), 'The search filters are helpful.');
    await user.click(screen.getByRole('button', { name: 'Send feedback' }));
    expect(await screen.findByRole('alert')).toBeTruthy();
    expect((screen.getByLabelText('Your feedback Required') as HTMLTextAreaElement).value).toBe('The search filters are helpful.');
    const firstKey = submitPlatformFeedback.mock.calls[0][1];
    expect(firstKey).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i);

    await user.click(screen.getByRole('button', { name: 'Send feedback' }));
    expect((await screen.findByRole('status')).textContent).toContain('Thank you for helping us improve.');
    expect(submitPlatformFeedback).toHaveBeenCalledTimes(2);
    expect(submitPlatformFeedback.mock.calls[1][1]).toBe(firstKey);
  });

  it('asks before discarding typed content and closes only after confirmation', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<FeedbackModal open onClose={onClose} />);
    await user.type(screen.getByLabelText('Your feedback Required'), 'A note worth keeping.');
    await user.keyboard('{Escape}');
    expect(screen.getByRole('alertdialog', { name: 'Discard feedback?' })).toBeTruthy();
    expect(onClose).not.toHaveBeenCalled();
    await user.click(screen.getByRole('button', { name: 'Discard' }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('traps keyboard focus in the discard confirmation until the member chooses', async () => {
    const user = userEvent.setup();
    render(<FeedbackModal open onClose={() => {}} />);
    await user.type(screen.getByLabelText('Your feedback Required'), 'Keep this thought.');
    await user.keyboard('{Escape}');
    const keepWriting = screen.getByRole('button', { name: 'Keep writing' });
    expect(document.activeElement).toBe(keepWriting);
    await user.keyboard('{Shift>}{Tab}{/Shift}');
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Discard' }));
  });

  it('returns focus to its invoking control when a clean modal is dismissed outside', async () => {
    const user = userEvent.setup();
    function Trigger() {
      const [open, setOpen] = useState(false);
      return <><button type="button" onClick={() => setOpen(true)}>Open feedback</button><FeedbackModal open={open} onClose={() => setOpen(false)} /></>;
    }
    render(<Trigger />);
    const trigger = screen.getByRole('button', { name: 'Open feedback' });
    await user.click(trigger);
    expect(await screen.findByRole('dialog')).toBeTruthy();
    await user.click(document.querySelector('[class*="backdrop"]') as HTMLElement);
    expect(screen.queryByRole('dialog')).toBeNull();
    await waitFor(() => expect(document.activeElement).toBe(trigger));
  });

  it('does not allow rapid duplicate submissions', async () => {
    const user = userEvent.setup();
    let resolveSubmission: (value: unknown) => void = () => {};
    submitPlatformFeedback.mockReturnValue(new Promise((resolve) => { resolveSubmission = resolve; }));
    render(<FeedbackModal open onClose={() => {}} />);
    await user.selectOptions(screen.getByLabelText(/What is this about/), 'Website / App');
    await user.type(screen.getByLabelText('Your feedback Required'), 'Please keep this note.');
    await user.dblClick(screen.getByRole('button', { name: 'Send feedback' }));
    expect(submitPlatformFeedback).toHaveBeenCalledTimes(1);
    resolveSubmission({ id: 'feedback-1' });
    expect(await screen.findByRole('status')).toBeTruthy();
  });

  it('requires a member to explicitly choose one category', async () => {
    const user = userEvent.setup();
    render(<FeedbackModal open onClose={() => {}} />);
    expect((screen.getByLabelText(/What is this about/) as HTMLSelectElement).value).toBe('');
    await user.type(screen.getByLabelText('Your feedback Required'), 'A useful observation.');
    await user.click(screen.getByRole('button', { name: 'Send feedback' }));
    expect(screen.getByRole('alert').textContent).toContain('choose a feedback category');
    expect(submitPlatformFeedback).not.toHaveBeenCalled();
  });
});