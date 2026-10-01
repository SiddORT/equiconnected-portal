import { apiClient } from './client';

export interface MessageAvailability {
  available: boolean;
  reason: 'provider_unavailable' | 'provider_account_unavailable' | 'provider_account_ambiguous' | 'messaging_encryption_unavailable' | null;
  provider_name: string | null;
}

export interface PrivateConversationSummary {
  id: string;
  provider_id: string;
  provider_name: string;
  member_name?: string | null;
  last_message_at: string | null;
  unread_count: number;
  last_sequence: number;
  notifications_failed: boolean;
}

export interface PrivateMessage {
  id: string;
  sequence: number;
  sender_side: 'member' | 'provider';
  created_at: string;
  body: string;
}

export interface MemberContactSnapshot {
  name: string;
  email: string;
  phone: string;
}

export interface PrivateConversation {
  conversation: PrivateConversationSummary;
  messages: PrivateMessage[];
  contact: MemberContactSnapshot | null;
  next_before_sequence: number | null;
  unread_count: number;
}

export interface PrivateInbox {
  items: PrivateConversationSummary[];
  page: number;
  page_size: number;
  total: number;
}

export interface PrivateMessageRequest {
  request_id: string;
  message: string;
}

export interface PrivateMessageReadResponse {
  read_sequence: number;
  read_sequences: number[];
}

export async function getMessageAvailability(providerId: string): Promise<MessageAvailability> {
  const { data } = await apiClient.get<MessageAvailability>('/messages/availability', {
    params: { provider_id: providerId },
  });
  return data;
}

export async function startPrivateConversation(body: {
  provider_id: string;
  request_id: string;
  message: string;
  consent: true;
}): Promise<PrivateConversation> {
  const { data } = await apiClient.post<PrivateConversation>('/messages/start', body);
  return data;
}

export async function listPrivateConversations(
  page = 1,
  pageSize = 20,
  signal?: AbortSignal,
): Promise<PrivateInbox> {
  const { data } = await apiClient.get<PrivateInbox>('/messages/inbox', {
    params: { page, page_size: pageSize },
    signal,
  });
  return data;
}

export async function getPrivateMessageUnreadCount(signal?: AbortSignal): Promise<number> {
  const { data } = await apiClient.get<{ count: number }>('/messages/unread', { signal });
  return data.count;
}

export async function getPrivateConversation(
  conversationId: string,
  options: { beforeSequence?: number; limit?: number; signal?: AbortSignal } = {},
): Promise<PrivateConversation> {
  const { data } = await apiClient.get<PrivateConversation>(`/messages/${conversationId}`, {
    params: {
      before_sequence: options.beforeSequence,
      limit: options.limit ?? 50,
    },
    signal: options.signal,
  });
  return data;
}

export async function replyToPrivateConversation(
  conversationId: string,
  body: PrivateMessageRequest,
): Promise<PrivateMessage> {
  const { data } = await apiClient.post<PrivateMessage>(
    `/messages/${conversationId}/messages`,
    body,
  );
  return data;
}

export async function markPrivateConversationRead(
  conversationId: string,
  messageSequences: number[],
  signal?: AbortSignal,
): Promise<PrivateMessageReadResponse> {
  const { data } = await apiClient.post<PrivateMessageReadResponse>(`/messages/${conversationId}/read`, {
    message_sequences: messageSequences,
  }, { signal });
  return data;
}

export function notifyMessagesUnreadChanged() {
  if (typeof window !== 'undefined') window.dispatchEvent(new Event('messages-unread-changed'));
}