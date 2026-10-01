// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import * as messagesApi from '@/api/messages';
import * as profileApi from '@/api/profile';
import { MemberMessagesPage, ProviderMessagesPage } from './PrivateMessagesPage';

vi.mock('@/app/AuthContext', () => ({
  useAuth: () => ({
    user: { id: 'member-1', email: 'member@example.com', full_name: 'Morgan Member', roles: ['horse_owner'] },
    logout: vi.fn(),
  }),
}));
vi.mock('@/api/profile', () => ({ getProfile: vi.fn() }));
vi.mock('@/api/messages', () => ({
  getMessageAvailability: vi.fn(),
  startPrivateConversation: vi.fn(),
  listPrivateConversations: vi.fn(),
  getPrivateMessageUnreadCount: vi.fn(),
  getPrivateConversation: vi.fn(),
  replyToPrivateConversation: vi.fn(),
  markPrivateConversationRead: vi.fn(),
  notifyMessagesUnreadChanged: vi.fn(),
}));

let visibleMessageFilter = (_element: Element) => true;

class TestIntersectionObserver {
  constructor(private readonly callback: IntersectionObserverCallback) {}

  observe(target: Element) {
    if (!visibleMessageFilter(target)) return;
    const bounds = target.getBoundingClientRect();
    this.callback([{
      target,
      isIntersecting: true,
      intersectionRatio: 1,
      boundingClientRect: bounds,
      intersectionRect: bounds,
      rootBounds: null,
      time: performance.now(),
    }], this as unknown as IntersectionObserver);
  }

  disconnect() {}
  unobserve() {}
  takeRecords() { return []; }
}

const profile = {
  first_name: 'Morgan',
  last_name: 'Member',
  email: 'member@example.com',
  mobile_number: '+1 512 555 0100',
  address: null,
  country: 'United States',
  state_province: null,
  city: 'Austin',
  postal_code: null,
  roles: ['horse_owner'],
  stable_profile: null,
  horses: [],
};

const contact = {
  name: 'Morgan Member',
  email: 'member@example.com',
  phone: '+1 512 555 0100',
};

function makeMessage(sequence: number, sender_side: 'member' | 'provider' = 'member', body = `Message ${sequence}`) {
  return {
    id: `message-${sequence}`,
    sequence,
    sender_side,
    created_at: `2026-08-31T12:${String(sequence % 60).padStart(2, '0')}:00Z`,
    body,
  };
}

function makeThread(
  messages = [makeMessage(1), makeMessage(2, 'provider', 'We will be in touch.')],
  nextBeforeSequence: number | null = null,
) {
  return {
    conversation: {
      id: 'conversation-1',
      provider_id: 'provider-1',
      provider_name: 'Ranch Equine Care',
      last_message_at: '2026-08-31T12:02:00Z',
      unread_count: 1,
      last_sequence: messages[messages.length - 1]?.sequence ?? 0,
      notifications_failed: false,
    },
    messages,
    contact,
    next_before_sequence: nextBeforeSequence,
    unread_count: 1,
  };
}

function renderMemberMessages(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/member/messages/:conversationId?" element={<MemberMessagesPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

function renderProviderMessages(path = '/provider/messages/conversation-1') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/provider/messages/:conversationId?" element={<ProviderMessagesPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.mocked(profileApi.getProfile).mockResolvedValue(profile);
  vi.mocked(messagesApi.getMessageAvailability).mockResolvedValue({
    available: true,
    reason: null,
    provider_name: 'Ranch Equine Care',
  });
  vi.mocked(messagesApi.listPrivateConversations).mockResolvedValue({
    items: [],
    page: 1,
    page_size: 20,
    total: 0,
  });
  vi.mocked(messagesApi.getPrivateMessageUnreadCount).mockResolvedValue(0);
  vi.mocked(messagesApi.getPrivateConversation).mockResolvedValue(makeThread());
  vi.mocked(messagesApi.startPrivateConversation).mockResolvedValue(makeThread());
  vi.mocked(messagesApi.replyToPrivateConversation).mockResolvedValue(makeMessage(3));
  vi.mocked(messagesApi.markPrivateConversationRead).mockImplementation(async (_id, sequences) => ({
    read_sequence: 0,
    read_sequences: sequences,
  }));
  visibleMessageFilter = () => true;
  Object.defineProperty(globalThis, 'IntersectionObserver', {
    configurable: true,
    value: TestIntersectionObserver,
  });
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.resetAllMocks();
  Object.defineProperty(document, 'hidden', { configurable: true, value: false });
});

describe('private member and provider messaging', () => {
  it('shows the server-derived contact preview and explicit consent, then sends only a provider ID, message and request ID', async () => {
    const user = userEvent.setup();
    vi.mocked(messagesApi.startPrivateConversation).mockResolvedValue(makeThread());
    const localWrite = vi.spyOn(window.localStorage, 'setItem');
    const sessionWrite = vi.spyOn(window.sessionStorage, 'setItem');

    renderMemberMessages('/member/messages?provider_id=provider-1');

    expect(await screen.findByRole('heading', { name: 'Ranch Equine Care' })).toBeTruthy();
    expect(screen.getByText('Morgan Member')).toBeTruthy();
    expect(screen.getByText('member@example.com')).toBeTruthy();
    expect(screen.getByText('+1 512 555 0100')).toBeTruthy();
    expect(screen.getByText(/not end-to-end encryption/i)).toBeTruthy();
    await user.type(screen.getByLabelText('Your message'), 'Could we discuss care options?');
    await user.click(screen.getByRole('checkbox', { name: /agree to share/i }));
    await user.click(screen.getByRole('button', { name: 'Send private message' }));

    await waitFor(() => expect(messagesApi.startPrivateConversation).toHaveBeenCalledTimes(1));
    const sent = vi.mocked(messagesApi.startPrivateConversation).mock.calls[0][0];
    expect(sent).toMatchObject({
      provider_id: 'provider-1',
      message: 'Could we discuss care options?',
      consent: true,
    });
    expect(sent.request_id).toMatch(/^[0-9a-f-]{36}$/i);
    expect(sent).not.toHaveProperty('email');
    expect(sent).not.toHaveProperty('name');
    expect(sent).not.toHaveProperty('phone');
    expect(localWrite).not.toHaveBeenCalled();
    expect(sessionWrite).not.toHaveBeenCalled();
    expect(await screen.findByText('We will be in touch.')).toBeTruthy();
  });

  it('shows consented contact links only in the provider thread and retries an uncertain reply with the same request ID', async () => {
    const user = userEvent.setup();
    vi.mocked(messagesApi.getPrivateConversation).mockResolvedValue(makeThread([
      makeMessage(1, 'member', '<img src=x onerror=alert(1)>'),
      makeMessage(2, 'provider', 'Thanks, I have your note.'),
    ]));
    vi.mocked(messagesApi.replyToPrivateConversation)
      .mockRejectedValueOnce(new Error('connection lost'))
      .mockResolvedValueOnce(makeMessage(3));

    renderProviderMessages();

    expect(await screen.findByText('Morgan Member')).toBeTruthy();
    expect(screen.getByText('<img src=x onerror=alert(1)>')).toBeTruthy();
    expect(document.querySelector('img[onerror]')).toBeNull();
    expect(screen.getByRole('link', { name: 'Email member' }).getAttribute('href')).toBe('mailto:member@example.com');
    expect(screen.getByRole('link', { name: 'Call member' }).getAttribute('href')).toBe('tel:+15125550100');

    await user.type(screen.getByLabelText('Reply'), 'Thank you for contacting us.');
    await user.click(screen.getByRole('button', { name: 'Send reply' }));
    const retry = await screen.findByRole('button', { name: 'Retry same message' });
    expect(screen.getByText(/same request identifier/i)).toBeTruthy();
    await user.click(retry);

    expect(messagesApi.replyToPrivateConversation).toHaveBeenCalledTimes(2);
    expect(vi.mocked(messagesApi.replyToPrivateConversation).mock.calls[0][1]).toEqual(
      vi.mocked(messagesApi.replyToPrivateConversation).mock.calls[1][1],
    );
    expect(await screen.findByRole('button', { name: 'Send reply' })).toBeTruthy();
  });

  it('explains notification failure without implying a saved message was lost', async () => {
    const thread = makeThread();
    thread.conversation.notifications_failed = true;
    vi.mocked(messagesApi.getPrivateConversation).mockResolvedValue(thread);

    renderMemberMessages('/member/messages/conversation-1');

    expect(await screen.findByText(
      'An email notification to your account could not be sent. Messages remain saved and available in your inbox.',
    )).toBeTruthy();
  });

  it('submits only exact visible message receipts without skipping older unseen messages', async () => {
    const recent = makeThread(
      Array.from({ length: 50 }, (_, index) => makeMessage(index + 2)),
      2,
    );
    const older = makeThread([makeMessage(1)], null);
    vi.mocked(messagesApi.getPrivateConversation).mockImplementation((_id, options) =>
      Promise.resolve(options?.beforeSequence ? older : recent),
    );
    visibleMessageFilter = (element) => ['1', '51'].includes(element.getAttribute('data-message-sequence') ?? '');
    const user = userEvent.setup();

    renderProviderMessages();
    await screen.findByText('Message 51');
    await waitFor(() => expect(messagesApi.markPrivateConversationRead).toHaveBeenCalledWith(
      'conversation-1', [51], expect.any(AbortSignal),
    ));

    await user.click(screen.getByRole('button', { name: 'Load older messages' }));
    await waitFor(() => expect(messagesApi.markPrivateConversationRead).toHaveBeenCalledWith(
      'conversation-1', [1], expect.any(AbortSignal),
    ));
  });

  it('does not fetch or mark a conversation read while the browser tab is hidden', async () => {
    Object.defineProperty(document, 'hidden', { configurable: true, value: true });

    renderProviderMessages();

    await act(async () => Promise.resolve());
    expect(messagesApi.getPrivateConversation).not.toHaveBeenCalled();
    expect(messagesApi.markPrivateConversationRead).not.toHaveBeenCalled();
  });
});