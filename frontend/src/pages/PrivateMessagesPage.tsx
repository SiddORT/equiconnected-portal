import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent, type RefObject } from 'react';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import * as messageApi from '@/api/messages';
import type {
  MemberContactSnapshot,
  MessageAvailability,
  PrivateConversation,
  PrivateConversationSummary,
  PrivateInbox,
  PrivateMessage,
} from '@/api/messages';
import { extractErrorMessage } from '@/api/client';
import { useAuth } from '@/app/AuthContext';
import { ProviderTopNav } from '@/components/layout/ProviderTopNav';
import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { getProfile } from '@/api/profile';
import type { MemberProfile } from '@/types';
import styles from './PrivateMessagesPage.module.css';

type PortalRole = 'member' | 'provider';
type Attempt = { requestId: string; message: string };

function formatMessageDate(value: string) {
  const timestamp = new Date(value);
  return Number.isNaN(timestamp.getTime())
    ? 'Time unavailable'
    : timestamp.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
}

function displayName(profile: MemberProfile | null) {
  return [profile?.first_name, profile?.last_name].filter((part) => part?.trim()).join(' ').trim();
}

function profileContact(profile: MemberProfile | null): MemberContactSnapshot | null {
  const name = displayName(profile);
  const email = profile?.email?.trim() ?? '';
  const phone = profile?.mobile_number?.trim() ?? '';
  return name && email && phone ? { name, email, phone } : null;
}

function unavailableReason(reason: MessageAvailability['reason']) {
  switch (reason) {
    case 'provider_unavailable':
      return 'This provider listing is not currently available for private messaging.';
    case 'provider_account_unavailable':
      return 'This provider does not currently have an active messaging account.';
    case 'provider_account_ambiguous':
      return 'This provider account needs attention before private messaging can be enabled.';
    case 'messaging_encryption_unavailable':
      return 'Private messaging is temporarily unavailable. The provider’s direct contact options are still available.';
    default:
      return 'Private messaging availability could not be confirmed. You can still use the provider’s direct contact options.';
  }
}

function safeEmailHref(email: string) {
  return `mailto:${email.trim()}`;
}

function safePhoneHref(phone: string) {
  const dialable = phone.replace(/[^\d+]/g, '');
  return /^\+?\d+$/.test(dialable) ? `tel:${dialable}` : null;
}

function MessageComposer({
  initial,
  value,
  onChange,
  onSubmit,
  onRetry,
  saving,
  retryPending,
  error,
}: {
  initial: boolean;
  value: string;
  onChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onRetry: () => void;
  saving: boolean;
  retryPending: boolean;
  error: string;
}) {
  const textareaId = initial ? 'first-private-message' : 'private-message-reply';
  return (
    <form className={styles.composer} onSubmit={onSubmit}>
      {error && <Alert variant="error">{error}</Alert>}
      <label className={styles.field} htmlFor={textareaId}>
        {initial ? 'Your message' : 'Reply'}
        <textarea
          id={textareaId}
          rows={5}
          maxLength={5000}
          value={value}
          disabled={saving || retryPending}
          onChange={(event) => onChange(event.target.value)}
          aria-describedby={`${textareaId}-help ${textareaId}-count`}
        />
      </label>
      <div className={styles.composerMeta}>
        <span id={`${textareaId}-help`}>Plain text only. Do not include sensitive medical or payment information.</span>
        <span id={`${textareaId}-count`}>{value.length}/5000</span>
      </div>
      <div className={styles.composerActions}>
        {retryPending
          ? <Button type="button" loading={saving} onClick={onRetry}>Retry same message</Button>
          : <Button type="submit" loading={saving}>{initial ? 'Send private message' : 'Send reply'}</Button>}
      </div>
      {retryPending && <p className={styles.retryHelp} role="status">
        We could not confirm whether that message was saved. Retrying sends the same request identifier, so a saved message will not be duplicated.
      </p>}
    </form>
  );
}

function ContactPreview({ contact }: { contact: MemberContactSnapshot }) {
  return (
    <dl className={styles.contactPreview}>
      <div><dt>Name</dt><dd>{contact.name}</dd></div>
      <div><dt>Account email</dt><dd>{contact.email}</dd></div>
      <div><dt>Phone</dt><dd>{contact.phone}</dd></div>
    </dl>
  );
}

function InboxList({
  role,
  inbox,
  loading,
  page,
  onPage,
  conversationId,
}: {
  role: PortalRole;
  inbox: PrivateInbox | null;
  loading: boolean;
  page: number;
  onPage: (next: number) => void;
  conversationId?: string;
}) {
  const basePath = role === 'member' ? '/member/messages' : '/provider/messages';
  const totalPages = inbox ? Math.max(1, Math.ceil(inbox.total / inbox.page_size)) : 1;
  return (
    <aside className={`${styles.inbox} ${conversationId ? styles.inboxOnThread : ''}`} aria-label="Message conversations">
      <h2>Inbox</h2>
      {loading && !inbox
        ? <p className={styles.muted} role="status">Loading your messages…</p>
        : !inbox?.items.length
          ? <p className={styles.muted}>Your inbox is empty. Conversations will appear here when a message is sent.</p>
          : <ul className={styles.conversationList}>
            {inbox.items.map((item: PrivateConversationSummary) => {
              const title = role === 'member' ? item.provider_name : item.member_name;
              return (
                <li key={item.id}>
                  <Link
                    to={`${basePath}/${item.id}`}
                    className={`${styles.conversationLink} ${conversationId === item.id ? styles.selectedConversation : ''}`}
                    aria-current={conversationId === item.id ? 'page' : undefined}
                  >
                    <span className={styles.conversationTitle}>{title || (role === 'member' ? 'Provider conversation' : 'Member conversation')}</span>
                    {item.last_message_at && <time dateTime={item.last_message_at}>{formatMessageDate(item.last_message_at)}</time>}
                    {item.unread_count > 0 && <span className={styles.unreadPill} aria-label={`${item.unread_count} unread messages`}>{item.unread_count > 99 ? '99+' : item.unread_count} unread</span>}
                    {item.notifications_failed && <span className={styles.notificationStatus}>Email notice failed</span>}
                  </Link>
                </li>
              );
            })}
          </ul>}
      {inbox && totalPages > 1 && <nav className={styles.pagination} aria-label="Inbox pages">
        <button type="button" disabled={page <= 1 || loading} onClick={() => onPage(page - 1)}>Previous</button>
        <span>Page {page} of {totalPages}</span>
        <button type="button" disabled={page >= totalPages || loading} onClick={() => onPage(page + 1)}>Next</button>
      </nav>}
    </aside>
  );
}

function Thread({
  conversation,
  role,
  messages,
  onLoadOlder,
  loadingOlder,
  bottomRef,
}: {
  conversation: PrivateConversation;
  role: PortalRole;
  messages: PrivateMessage[];
  onLoadOlder: () => void;
  loadingOlder: boolean;
  bottomRef: RefObject<HTMLLIElement | null>;
}) {
  const contact = conversation.contact;
  return (
    <>
      {role === 'provider' && contact && <section className={styles.memberContact} aria-labelledby="member-contact-title">
        <div><p className={styles.eyebrow}>Shared with your provider account</p><h2 id="member-contact-title">Member contact</h2></div>
        <ContactPreview contact={contact} />
        <div className={styles.directActions}>
          <a href={safeEmailHref(contact.email)}>Email member</a>
          {safePhoneHref(contact.phone) && <a href={safePhoneHref(contact.phone)!}>Call member</a>}
        </div>
      </section>}
      {conversation.next_before_sequence !== null && <div className={styles.olderAction}>
        <Button variant="ghost" type="button" loading={loadingOlder} onClick={onLoadOlder}>Load older messages</Button>
      </div>}
      <ol className={styles.thread} aria-label="Conversation messages">
        {messages.map((message) => {
          const ownMessage = (role === 'member' && message.sender_side === 'member')
            || (role === 'provider' && message.sender_side === 'provider');
          return (
            <li
              className={`${styles.message} ${ownMessage ? styles.ownMessage : ''}`}
              data-message-sequence={message.sequence}
              data-message-received={ownMessage ? 'false' : 'true'}
              key={`${message.sequence}-${message.id}`}
            >
              <div className={styles.messageHeading}>
                <strong>{ownMessage ? 'You' : (role === 'member' ? conversation.conversation.provider_name : contact?.name) || (role === 'member' ? 'Provider' : 'Member')}</strong>
                <time dateTime={message.created_at}>{formatMessageDate(message.created_at)}</time>
              </div>
              <p>{message.body}</p>
            </li>
          );
        })}
        <li ref={bottomRef} className={styles.threadEnd} aria-hidden="true" />
      </ol>
    </>
  );
}

function PrivateMessagesPage({ role }: { role: PortalRole }) {
  const { user } = useAuth();
  const { conversationId } = useParams<{ conversationId?: string }>();
  const location = useLocation();
  const navigate = useNavigate();
  const providerId = role === 'member' ? new URLSearchParams(location.search).get('provider_id') : null;
  const selectedProviderId = providerId?.trim() || null;
  const [page, setPage] = useState(1);
  const [inbox, setInbox] = useState<PrivateInbox | null>(null);
  const [inboxLoading, setInboxLoading] = useState(true);
  const [inboxError, setInboxError] = useState('');
  const [reloadKey, setReloadKey] = useState(0);
  const [conversation, setConversation] = useState<PrivateConversation | null>(null);
  const [threadLoading, setThreadLoading] = useState(false);
  const [threadError, setThreadError] = useState('');
  const [profile, setProfile] = useState<MemberProfile | null>(null);
  const [availability, setAvailability] = useState<MessageAvailability | null>(null);
  const [startLoading, setStartLoading] = useState(false);
  const [startError, setStartError] = useState('');
  const [startLoadingError, setStartLoadingError] = useState('');
  const [consent, setConsent] = useState(false);
  const [firstDraft, setFirstDraft] = useState('');
  const [replyDraft, setReplyDraft] = useState('');
  const [sendError, setSendError] = useState('');
  const [sending, setSending] = useState(false);
  const [attempt, setAttempt] = useState<Attempt | null>(null);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const [pageVisible, setPageVisible] = useState(!document.hidden);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const bottomRef = useRef<HTMLLIElement>(null);
  const threadContentRef = useRef<HTMLDivElement>(null);
  const pageRequest = useRef(0);
  const sendingRef = useRef(false);
  const attemptRef = useRef<Attempt | null>(null);
  const conversationRef = useRef(conversation);
  const activeRouteRef = useRef(conversationId);
  const readReceipts = useRef<Record<string, Set<number>>>({});
  conversationRef.current = conversation;
  activeRouteRef.current = conversationId;

  const pathBase = role === 'member' ? '/member/messages' : '/provider/messages';
  const contact = profileContact(profile);
  const providerName = availability?.provider_name ?? 'this provider';
  const profileComplete = contact !== null;
  const routeTitle = useMemo(() => role === 'member' ? providerName : 'Member conversation', [providerName, role]);

  useEffect(() => {
    const onVisibilityChange = () => setPageVisible(!document.hidden);
    document.addEventListener('visibilitychange', onVisibilityChange);
    return () => document.removeEventListener('visibilitychange', onVisibilityChange);
  }, []);

  useEffect(() => {
    if (role !== 'member' || !selectedProviderId) {
      setProfile(null);
      setAvailability(null);
      setStartLoadingError('');
      setConsent(false);
      setFirstDraft('');
      setStartError('');
      return;
    }
    let active = true;
    const controller = new AbortController();
    setStartLoading(true);
    setStartLoadingError('');
    Promise.all([getProfile(), messageApi.getMessageAvailability(selectedProviderId)])
      .then(([nextProfile, nextAvailability]) => {
        if (!active) return;
        setProfile(nextProfile);
        setAvailability(nextAvailability);
      })
      .catch((error) => {
        if (active && !controller.signal.aborted) {
          setStartLoadingError(extractErrorMessage(error, 'Your contact preview and provider messaging availability could not be loaded.'));
        }
      })
      .finally(() => {
        if (active) setStartLoading(false);
      });
    return () => {
      active = false;
      controller.abort();
    };
  }, [role, selectedProviderId]);

  useEffect(() => {
    if (!user?.id) {
      setInbox(null);
      setConversation(null);
      setInboxLoading(false);
      setThreadLoading(false);
      return;
    }
    let active = true;
    let timer: number | undefined;
    let currentController: AbortController | null = null;
    let requestEpoch = ++pageRequest.current;

    const refresh = async (showLoading = false) => {
      if (!active || document.hidden) return;
      requestEpoch = ++pageRequest.current;
      const requestId = requestEpoch;
      currentController?.abort();
      const controller = new AbortController();
      currentController = controller;
      if (showLoading) {
        setInboxLoading(!inbox);
        if (conversationId) setThreadLoading(!conversation);
      }
      const requests: Promise<unknown>[] = [
        messageApi.listPrivateConversations(page, 20, controller.signal),
      ];
      if (conversationId) requests.push(messageApi.getPrivateConversation(conversationId, { limit: 50, signal: controller.signal }));
      const results = await Promise.allSettled(requests);
      if (!active || requestId !== pageRequest.current || controller.signal.aborted) return;
      const [inboxResult, threadResult] = results;
      if (inboxResult.status === 'fulfilled') {
        const nextInbox = inboxResult.value as PrivateInbox;
        setInbox(nextInbox);
        setInboxError('');
      } else if (!controller.signal.aborted) {
        setInboxError(extractErrorMessage(inboxResult.reason, 'Your messages could not be loaded.'));
      }
      setInboxLoading(false);
      if (conversationId) {
        if (threadResult?.status === 'fulfilled') {
          const next = threadResult.value as PrivateConversation;
          if (activeRouteRef.current === conversationId) {
            const previous = conversationRef.current?.conversation.id === conversationId
              ? conversationRef.current.messages : [];
            const merged = new Map<number, PrivateMessage>();
            [...previous, ...next.messages].forEach((item) => merged.set(item.sequence, item));
            const messages = [...merged.values()].sort((a, b) => a.sequence - b.sequence);
            const hasLoadedHistory = previous.length > 0
              && conversationRef.current?.next_before_sequence === null;
            const nextCursor = hasLoadedHistory
              || messages[0]?.sequence === 1
              ? null
              : next.next_before_sequence;
            setConversation({ ...next, messages, next_before_sequence: nextCursor });
            setThreadError('');
          }
        } else if (threadResult?.status === 'rejected' && !controller.signal.aborted) {
          setThreadError(extractErrorMessage(threadResult.reason, 'This conversation could not be opened.'));
        }
        setThreadLoading(false);
      } else {
        setConversation(null);
        setThreadError('');
      }
      if (active && requestId === pageRequest.current && !document.hidden) {
        timer = window.setTimeout(() => void refresh(false), 15_000);
      }
    };

    const onVisibilityChange = () => {
      if (document.hidden) {
        window.clearTimeout(timer);
        currentController?.abort();
      } else {
        void refresh(false);
      }
    };
    const onUnreadChange = () => {
      if (!conversationId && !document.hidden) void refresh(false);
    };
    document.addEventListener('visibilitychange', onVisibilityChange);
    window.addEventListener('messages-unread-changed', onUnreadChange);
    void refresh(true);
    return () => {
      active = false;
      pageRequest.current += 1;
      window.clearTimeout(timer);
      currentController?.abort();
      document.removeEventListener('visibilitychange', onVisibilityChange);
      window.removeEventListener('messages-unread-changed', onUnreadChange);
    };
  }, [user?.id, role, page, conversationId, reloadKey]);

  useEffect(() => {
    if (conversationId) {
      headingRef.current?.focus({ preventScroll: true });
    }
    setAttempt(null);
    attemptRef.current = null;
    setSendError('');
    setThreadError('');
    setReplyDraft('');
  }, [conversationId, selectedProviderId]);

  useEffect(() => {
    if (
      !pageVisible
      || document.hidden
      || !user?.id
      || !conversationId
      || conversation?.conversation.id !== conversationId
      || !conversation.messages.length
    ) return;

    const content = threadContentRef.current;
    const messageList = content?.querySelector('[aria-label="Conversation messages"]');
    if (!messageList) return;
    const receiptKey = `${user.id}:${conversationId}`;
    let cancelled = false;
    let timer: number | undefined;
    const controllers = new Set<AbortController>();
    const visibleSequences = new Set<number>();
    const attemptedSequences = new Set<number>();
    const receipts = readReceipts.current[receiptKey] ?? new Set<number>();
    readReceipts.current[receiptKey] = receipts;

    const flushVisibleSequences = () => {
      timer = undefined;
      if (
        cancelled
        || document.hidden
        || activeRouteRef.current !== conversationId
        || !messageList.isConnected
      ) return;
      const sequences = [...visibleSequences]
        .filter((sequence) => !receipts.has(sequence) && !attemptedSequences.has(sequence))
        .sort((a, b) => a - b)
        .slice(0, 100);
      if (!sequences.length) return;
      sequences.forEach((sequence) => {
        visibleSequences.delete(sequence);
        attemptedSequences.add(sequence);
      });
      const controller = new AbortController();
      controllers.add(controller);
      void messageApi.markPrivateConversationRead(conversationId, sequences, controller.signal)
        .then((result) => {
          if (cancelled || activeRouteRef.current !== conversationId) return;
          result.read_sequences.forEach((sequence) => receipts.add(sequence));
          if (result.read_sequences.length) messageApi.notifyMessagesUnreadChanged();
        })
        .catch(() => {
          // A later foreground refresh can retry messages that remain unread.
        })
        .finally(() => {
          controllers.delete(controller);
          if (!cancelled && visibleSequences.size && timer === undefined) {
            timer = window.setTimeout(flushVisibleSequences, 20);
          }
        });
    };
    const queueVisibleSequences = (sequences: number[]) => {
      sequences.forEach((sequence) => visibleSequences.add(sequence));
      if (timer === undefined) timer = window.setTimeout(flushVisibleSequences, 20);
    };

    let observer: IntersectionObserver | null = null;
    if (typeof IntersectionObserver === 'undefined') {
      const visible = Array.from(messageList.querySelectorAll<HTMLElement>('[data-message-received="true"]'))
        .filter((element) => {
          const bounds = element.getBoundingClientRect();
          return bounds.width > 0
            && bounds.height > 0
            && bounds.top < window.innerHeight
            && bounds.bottom > 0
            && bounds.left < window.innerWidth
            && bounds.right > 0;
        })
        .map((element) => Number(element.dataset.messageSequence))
        .filter(Number.isInteger);
      queueVisibleSequences(visible);
    } else {
      observer = new IntersectionObserver((entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting && entry.intersectionRatio > 0)
          .map((entry) => {
            const target = entry.target as HTMLElement;
            return target.dataset.messageReceived === 'true'
              ? Number(target.dataset.messageSequence)
              : NaN;
          })
          .filter((sequence) => Number.isInteger(sequence));
        queueVisibleSequences(visible);
      }, { threshold: 0 });
      messageList.querySelectorAll<HTMLElement>('[data-message-sequence]').forEach((element) => {
        observer?.observe(element);
      });
    }
    return () => {
      cancelled = true;
      observer?.disconnect();
      if (timer !== undefined) window.clearTimeout(timer);
      controllers.forEach((controller) => controller.abort());
    };
  }, [conversation, conversationId, pageVisible, user?.id]);

  const beginAttempt = (message: string) => {
    const next = attemptRef.current ?? {
      requestId: window.crypto.randomUUID(),
      message: message.trim(),
    };
    attemptRef.current = next;
    setAttempt(next);
    return next;
  };

  const send = async (initial: boolean) => {
    if (sendingRef.current || !user?.id) return;
    const draft = initial ? firstDraft : replyDraft;
    if (!attemptRef.current && !draft.trim()) {
      setSendError('Write a message before sending.');
      return;
    }
    if (initial && !consent && !attemptRef.current) {
      setSendError('Please agree to share the contact details shown above with this provider.');
      return;
    }
    if (initial && !selectedProviderId) return;
    const currentAttempt = beginAttempt(draft);
    sendingRef.current = true;
    setSending(true);
    setSendError('');
    try {
      if (initial) {
        const result = await messageApi.startPrivateConversation({
          provider_id: selectedProviderId!,
          request_id: currentAttempt.requestId,
          message: currentAttempt.message,
          consent: true,
        });
        setFirstDraft('');
        attemptRef.current = null;
        setAttempt(null);
        messageApi.notifyMessagesUnreadChanged();
        navigate(`${pathBase}/${result.conversation.id}`, { replace: true });
      } else if (conversationId) {
        await messageApi.replyToPrivateConversation(conversationId, {
          request_id: currentAttempt.requestId,
          message: currentAttempt.message,
        });
        setReplyDraft('');
        attemptRef.current = null;
        setAttempt(null);
        messageApi.notifyMessagesUnreadChanged();
        try {
          const nextThread = await messageApi.getPrivateConversation(conversationId, { limit: 50 });
          if (activeRouteRef.current === conversationId) {
            const previous = conversationRef.current?.conversation.id === conversationId
              ? conversationRef.current : null;
            const merged = new Map<number, PrivateMessage>();
            [...(previous?.messages ?? []), ...nextThread.messages]
              .forEach((message) => merged.set(message.sequence, message));
            const messages = [...merged.values()].sort((a, b) => a.sequence - b.sequence);
            setConversation({
              ...nextThread,
              messages,
              next_before_sequence: previous?.next_before_sequence === null
                || messages[0]?.sequence === 1
                ? null
                : nextThread.next_before_sequence,
            });
            setThreadError('');
          }
        } catch {
          // The reply is committed; the foreground poll will refresh the thread.
        }
        try {
          const nextInbox = await messageApi.listPrivateConversations(page, 20);
          setInbox(nextInbox);
          setInboxError('');
        } catch {
          // The reply is committed; preserve the current inbox until the next poll.
        }
      }
    } catch (error) {
      const status = (error as { response?: { status?: number } })?.response?.status;
      if (typeof status === 'number' && status >= 400 && status < 500) {
        attemptRef.current = null;
        setAttempt(null);
      }
      setSendError(extractErrorMessage(
        error,
        'We could not confirm whether your message was saved. Retry the same message before starting a new one.',
      ));
    } finally {
      sendingRef.current = false;
      setSending(false);
    }
  };

  const submit = (initial: boolean) => (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    void send(initial);
  };

  const loadOlder = useCallback(async () => {
    if (!conversationId || loadingOlder || !conversation) return;
    const oldest = conversation.messages[0]?.sequence;
    if (!oldest || oldest <= 1) return;
    const activeId = conversationId;
    setLoadingOlder(true);
    try {
      const previous = await messageApi.getPrivateConversation(activeId, {
        beforeSequence: oldest,
        limit: 50,
      });
      if (activeRouteRef.current !== activeId) return;
      setConversation((current) => {
        if (!current || current.conversation.id !== activeId) return current;
        const merged = new Map<number, PrivateMessage>();
        [...previous.messages, ...current.messages].forEach((message) => merged.set(message.sequence, message));
        return {
          ...current,
          messages: [...merged.values()].sort((a, b) => a.sequence - b.sequence),
          next_before_sequence: previous.messages[0]?.sequence === 1
            ? null
            : previous.next_before_sequence,
        };
      });
    } catch (error) {
      setThreadError(extractErrorMessage(error, 'Older messages could not be loaded.'));
    } finally {
      setLoadingOlder(false);
    }
  }, [conversation, conversationId, loadingOlder]);

  const inboxPageChange = (nextPage: number) => {
    setInboxLoading(true);
    setPage(Math.max(1, nextPage));
  };

  const selectedThread = Boolean(conversationId);
  const startMode = role === 'member' && Boolean(selectedProviderId) && !selectedThread;
  const showInbox = !startMode;
  const threadMatchesRoute = conversation?.conversation.id === conversationId;

  return (
    <div className={styles.page}>
      {role === 'provider' && <ProviderTopNav />}
      <main className={styles.shell}>
        <header className={styles.pageHeader}>
          <div>
            <p className={styles.eyebrow}>Private conversations</p>
            <h1 ref={headingRef} tabIndex={-1}>{role === 'member' ? 'Messages' : 'Provider messages'}</h1>
            <p>Private conversations with the provider account linked to this listing.</p>
          </div>
          {selectedThread && <Link className={styles.backLink} to={pathBase}>← Back to inbox</Link>}
        </header>

        {inboxError && <Alert variant="error">{inboxError}<button type="button" onClick={() => { setInboxLoading(true); setReloadKey((key) => key + 1); }}>Retry loading inbox</button></Alert>}
        <div className={`${styles.workspace} ${selectedThread || startMode ? styles.workspaceThread : ''} ${startMode ? styles.workspaceStart : ''}`}>
          {showInbox && <InboxList
            role={role}
            inbox={inbox}
            loading={inboxLoading}
            page={page}
            onPage={inboxPageChange}
            conversationId={conversationId}
          />}

          <section className={styles.threadPanel} aria-label={startMode ? 'Start a conversation' : 'Conversation'}>
            {startMode
              ? <div className={styles.startPanel}>
                <div className={styles.threadHeader}>
                  <p className={styles.eyebrow}>New private conversation</p>
                  <h2>{providerName}</h2>
                </div>
                {startLoading
                  ? <p role="status">Loading provider availability and your contact preview…</p>
                  : startLoadingError
                    ? <Alert variant="error">{startLoadingError}</Alert>
                    : !availability?.available
                      ? <div className={styles.unavailable}>
                        <p>{unavailableReason(availability?.reason ?? null)}</p>
                        <Link className={styles.actionLink} to={`/providers/${selectedProviderId}#contact`}>View direct contact options</Link>
                      </div>
                      : <>
                        <section className={styles.sharePreview} aria-labelledby="sharing-title">
                          <p className={styles.eyebrow}>Contact details shared with this provider only</p>
                          <h3 id="sharing-title">Before you send</h3>
                          {contact
                            ? <ContactPreview contact={contact} />
                            : <div className={styles.incompleteProfile}>
                              <p>Your name, account email, and phone number must be complete before you can start a conversation.</p>
                              <Link className={styles.actionLink} to="/profile?section=personal">Complete your account profile</Link>
                            </div>}
                          <p className={styles.privacyNote}>Your message and shared contact details are encrypted while stored and protected in transit. This is not end-to-end encryption.</p>
                        </section>
                        {profileComplete && <label className={styles.consent}>
                          <input type="checkbox" checked={consent} disabled={sending || attempt !== null} onChange={(event) => { setConsent(event.target.checked); setStartError(''); }} />
                          <span>I agree to share the contact details shown above with {providerName} so they can respond to me.</span>
                        </label>}
                        <MessageComposer
                          initial
                          value={firstDraft}
                          onChange={setFirstDraft}
                          onSubmit={submit(true)}
                          onRetry={() => void send(true)}
                          saving={sending}
                          retryPending={attempt !== null}
                          error={startError || sendError}
                        />
                      </>}
              </div>
              : selectedThread
                ? <div className={styles.activeThread} ref={threadContentRef}>
                  {threadError && <Alert variant="error">{threadError}<button type="button" onClick={() => { setThreadError(''); setReloadKey((key) => key + 1); }}>Retry loading conversation</button></Alert>}
                  {threadLoading && !threadMatchesRoute
                    ? <p className={styles.loading} role="status">Loading private conversation…</p>
                    : threadMatchesRoute && conversation
                      ? <>
                        <div className={styles.threadHeader}>
                          <p className={styles.eyebrow}>Private conversation</p>
                          <h2>{role === 'member' ? conversation.conversation.provider_name || routeTitle : conversation.contact?.name || 'Member conversation'}</h2>
                        </div>
                        {conversation.conversation.notifications_failed && (
                          <p className={styles.notificationNote} role="status">
                            An email notification to your account could not be sent. Messages remain saved and available in your inbox.
                          </p>
                        )}
                        <Thread
                          conversation={conversation}
                          role={role}
                          messages={conversation.messages}
                          onLoadOlder={() => void loadOlder()}
                          loadingOlder={loadingOlder}
                          bottomRef={bottomRef}
                        />
                        <MessageComposer
                          initial={false}
                          value={replyDraft}
                          onChange={setReplyDraft}
                          onSubmit={submit(false)}
                          onRetry={() => void send(false)}
                          saving={sending}
                          retryPending={attempt !== null}
                          error={sendError}
                        />
                      </>
                      : !threadError && <p className={styles.loading} role="status">Opening conversation…</p>}
                </div>
                : <div className={styles.inboxPrompt}>
                  <span className={styles.messageMark} aria-hidden="true">✉</span>
                  <h2>{inbox?.items.length ? 'Choose a conversation' : 'Your inbox is ready'}</h2>
                  <p>{inbox?.items.length ? 'Select a conversation to read and reply.' : role === 'member' ? 'Open a provider profile to start a private conversation.' : 'Member conversations will appear here when they write to your provider account.'}</p>
                  {role === 'member' && !inbox?.items.length && <Link className={styles.actionLink} to="/providers">Find a provider</Link>}
                </div>}
          </section>
        </div>
        <p className={styles.securityFooter}>Conversations are visible only to their member and the provider account explicitly linked to the listing. Messages are encrypted at rest and protected in transit over HTTPS; they are not end-to-end encrypted.</p>
      </main>
    </div>
  );
}

export function MemberMessagesPage() {
  return <PrivateMessagesPage role="member" />;
}

export function ProviderMessagesPage() {
  return <PrivateMessagesPage role="provider" />;
}