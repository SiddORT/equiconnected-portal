// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import * as messagesApi from '@/api/messages';
import * as profileApi from '@/api/profile';
import * as memberFeedbackApi from '@/api/memberFeedback';
import * as providersApi from '@/api/providers';
import { AppRouter } from './Router';

const { authState, recordMemberTrafficView } = vi.hoisted(() => ({
  authState: {
    user: null as null | {
      id: string;
      email: string;
      full_name: string;
      role: string;
      roles: string[];
      email_verified_at: string;
      is_active: boolean;
    },
    logout: vi.fn(),
  },
  recordMemberTrafficView: vi.fn(),
}));

vi.mock('@/app/AuthContext', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/app/AuthContext')>()),
  useAuth: () => ({
    isAuthenticated: true,
    isLoading: false,
    user: authState.user,
    logout: authState.logout,
    login: vi.fn(),
  }),
}));

vi.mock('@/api/messages', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api/messages')>()),
  getMessageAvailability: vi.fn(),
  startPrivateConversation: vi.fn(),
  listPrivateConversations: vi.fn(),
  getPrivateMessageUnreadCount: vi.fn(),
  getPrivateConversation: vi.fn(),
  replyToPrivateConversation: vi.fn(),
  markPrivateConversationRead: vi.fn(),
}));

vi.mock('@/api/profile', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api/profile')>()),
  getProfile: vi.fn(),
}));

vi.mock('@/api/memberFeedback', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api/memberFeedback')>()),
  getRecentMemberHistory: vi.fn(),
}));

vi.mock('@/api/providers', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api/providers')>()),
  getMemberProvider: vi.fn(),
  saveMemberProvider: vi.fn(),
  removeSavedMemberProvider: vi.fn(),
}));

vi.mock('@/api/memberHistoryRecording', () => ({
  recordMemberHistory: vi.fn().mockResolvedValue(undefined),
}));

vi.mock('@/analytics/trafficTracking', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/analytics/trafficTracking')>()),
  recordMemberTrafficView,
}));

vi.mock('@/app/TimeSettingsContext', () => ({
  systemCalendarDate: () => '2026-08-31',
  useTimeSettings: () => ({
    settings: { timezone: 'UTC' },
    isLoading: false,
    error: null,
    formatTimestamp: (value: string) => value,
  }),
}));

const member = {
  id: 'member-synthetic-1',
  email: 'morgan@example.test',
  full_name: 'Morgan Member',
  role: 'horse_owner',
  roles: ['horse_owner'],
  email_verified_at: '2026-08-01T00:00:00Z',
  is_active: true,
};

const provider = {
  ...member,
  id: 'provider-synthetic-1',
  email: 'ranch@example.test',
  full_name: 'Ranch Provider',
  role: 'provider',
  roles: ['provider'],
};

const memberProfile = {
  first_name: 'Morgan',
  last_name: 'Member',
  email: 'morgan@example.test',
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
  email: 'morgan@example.test',
  phone: '+1 512 555 0100',
};

const message = {
  id: 'message-synthetic-1',
  sequence: 1,
  sender_side: 'provider' as const,
  created_at: '2026-08-31T12:00:00Z',
  body: 'Synthetic message for this router test.',
};

const thread = {
  conversation: {
    id: 'conversation-synthetic-1',
    provider_id: 'provider-synthetic-1',
    provider_name: 'Ranch Equine Care',
    member_name: 'Morgan Member',
    last_message_at: '2026-08-31T12:00:00Z',
    unread_count: 0,
    last_sequence: 1,
    notifications_failed: false,
  },
  messages: [message],
  contact,
  next_before_sequence: null,
  unread_count: 0,
};

const inbox = {
  items: [thread.conversation],
  page: 1,
  page_size: 20,
  total: 1,
};

const providerDetail = {
  id: 'provider-synthetic-1',
  is_saved: false,
  provider_type: 'CLINIC' as const,
  name: 'Ranch Equine Care',
  description: 'Synthetic provider description.',
  thumbnail_url: null,
  thumbnail_alt_text: null,
  website: null,
  email: null,
  phone: null,
  visit_stability: 'NOT_STABLE_VISIT' as const,
  location: { city: 'Austin', state_province: 'Texas', country: 'United States' },
  average_rating: null,
  review_count: 0,
  distance_km: null,
  visible_reviews: [],
  own_review: null,
};

function setLocation(path: string) {
  window.history.replaceState({}, '', path);
}

function expectMemberMessagesNavigation() {
  expect(document.querySelectorAll('header[role="banner"]')).toHaveLength(1);
  const navs = screen.getAllByRole('navigation', { name: 'Member navigation' });
  expect(navs).toHaveLength(1);
  expect(screen.queryByRole('navigation', { name: 'Provider navigation' })).toBeNull();
  const messagesLink = within(navs[0]).getAllByRole('link', { name: 'Messages' });
  expect(messagesLink).toHaveLength(1);
  expect(messagesLink[0].getAttribute('href')).toBe('/member/messages');
  expect(messagesLink[0].getAttribute('aria-current')).toBe('page');
  expect(screen.getByRole('button', { name: 'Open member navigation' }).getAttribute('aria-expanded')).toBe('false');
}

function expectProviderMessagesNavigation() {
  expect(document.querySelectorAll('header[role="banner"]')).toHaveLength(1);
  const navs = screen.getAllByRole('navigation', { name: 'Provider navigation' });
  expect(navs).toHaveLength(1);
  expect(screen.queryByRole('navigation', { name: 'Member navigation' })).toBeNull();
  const messagesLink = within(navs[0]).getAllByRole('link', { name: 'Messages' });
  expect(messagesLink).toHaveLength(1);
  expect(messagesLink[0].getAttribute('href')).toBe('/provider/messages');
  expect(messagesLink[0].getAttribute('aria-current')).toBe('page');
  expect(within(navs[0]).getByRole('link', { name: 'Account' })).toBeTruthy();
  expect(within(navs[0]).getByRole('link', { name: 'Insights' })).toBeTruthy();
  expect(screen.queryByRole('button', { name: /member navigation/i })).toBeNull();
}

beforeEach(() => {
  authState.user = member;
  vi.mocked(profileApi.getProfile).mockResolvedValue(memberProfile);
  vi.mocked(memberFeedbackApi.getRecentMemberHistory).mockResolvedValue([]);
  vi.mocked(messagesApi.getMessageAvailability).mockResolvedValue({
    available: true,
    reason: null,
    provider_name: 'Ranch Equine Care',
  });
  vi.mocked(messagesApi.startPrivateConversation).mockResolvedValue(thread);
  vi.mocked(messagesApi.listPrivateConversations).mockResolvedValue(inbox);
  vi.mocked(messagesApi.getPrivateMessageUnreadCount).mockResolvedValue(0);
  vi.mocked(messagesApi.getPrivateConversation).mockResolvedValue(thread);
  vi.mocked(messagesApi.replyToPrivateConversation).mockResolvedValue(message);
  vi.mocked(messagesApi.markPrivateConversationRead).mockResolvedValue({
    read_sequence: 0,
    read_sequences: [],
  });
  vi.mocked(providersApi.getMemberProvider).mockResolvedValue(providerDetail);
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  window.history.replaceState({}, '', '/');
});

describe('AppRouter messages routes', () => {
  it.each([
    ['/member/messages', 'inbox'],
    ['/member/messages/conversation-synthetic-1', 'thread'],
    ['/member/messages?provider_id=provider-synthetic-1', 'provider start'],
  ])('loads a member %s route with one member banner/navigation and active Messages link', async (path, view) => {
    setLocation(path);
    render(<AppRouter />);

    expect(await screen.findByRole('heading', { level: 1, name: 'Messages' })).toBeTruthy();
    expectMemberMessagesNavigation();
    if (view === 'inbox') {
      expect(await screen.findByRole('heading', { level: 2, name: 'Inbox' })).toBeTruthy();
      expect(await screen.findByRole('link', { name: /Ranch Equine Care/ })).toBeTruthy();
    } else if (view === 'thread') {
      expect(await screen.findByText('Synthetic message for this router test.')).toBeTruthy();
      expect(document.activeElement).toBe(screen.getByRole('heading', { level: 1, name: 'Messages' }));
      expect(messagesApi.getPrivateConversation).toHaveBeenCalledWith(
        'conversation-synthetic-1',
        expect.objectContaining({ limit: 50, signal: expect.any(AbortSignal) }),
      );
    } else {
      expect(await screen.findByRole('heading', { level: 2, name: 'Ranch Equine Care' })).toBeTruthy();
      expect(messagesApi.getMessageAvailability).toHaveBeenCalledWith('provider-synthetic-1');
    }
  });

  it('loads provider messages with a single provider banner/navigation and focuses the deep-linked thread heading', async () => {
    authState.user = provider;
    setLocation('/provider/messages/conversation-synthetic-1');
    render(<AppRouter />);

    const heading = await screen.findByRole('heading', { level: 1, name: 'Provider messages' });
    expect(await screen.findByText('Synthetic message for this router test.')).toBeTruthy();
    expectProviderMessagesNavigation();
    expect(document.activeElement).toBe(heading);
    expect(messagesApi.getPrivateConversation).toHaveBeenCalledWith(
      'conversation-synthetic-1',
      expect.objectContaining({ limit: 50, signal: expect.any(AbortSignal) }),
    );
  });

  it('navigates from the actual provider detail message entry into member start mode', async () => {
    const user = userEvent.setup();
    setLocation('/providers/provider-synthetic-1');
    render(<AppRouter />);

    expect(await screen.findByRole('heading', { level: 1, name: 'Ranch Equine Care' })).toBeTruthy();
    const messageProvider = await screen.findByRole('link', { name: 'Message provider' });
    expect(messageProvider.getAttribute('href')).toBe('/member/messages?provider_id=provider-synthetic-1');
    await user.click(messageProvider);

    expect(await screen.findByRole('heading', { level: 2, name: 'Ranch Equine Care' })).toBeTruthy();
    expectMemberMessagesNavigation();
    expect(messagesApi.getMessageAvailability).toHaveBeenCalledWith('provider-synthetic-1');
  });

  it('keeps the member navigation menu toggle and role-specific links available', async () => {
    const user = userEvent.setup();
    setLocation('/member/messages');
    render(<AppRouter />);

    const toggle = screen.getByRole('button', { name: 'Open member navigation' });
    await user.click(toggle);
    expect(screen.getByRole('button', { name: 'Close member navigation' }).getAttribute('aria-expanded')).toBe('true');
    const nav = screen.getByRole('navigation', { name: 'Member navigation' });
    expect(within(nav).getByRole('link', { name: 'Providers' })).toBeTruthy();
    expect(within(nav).getByRole('link', { name: 'Profile' })).toBeTruthy();
    expect(within(nav).getByRole('link', { name: 'Saved providers' })).toBeTruthy();
    expect(within(nav).getByRole('link', { name: 'Messages' }).getAttribute('aria-current')).toBe('page');
  });
});