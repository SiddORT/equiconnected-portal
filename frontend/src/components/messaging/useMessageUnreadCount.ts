import { useEffect, useState } from 'react';
import { getPrivateMessageUnreadCount } from '@/api/messages';

const REFRESH_MS = 30_000;

export function useMessageUnreadCount(userId: string | undefined) {
  const [count, setCount] = useState(0);

  useEffect(() => {
    if (!userId) {
      setCount(0);
      return;
    }

    let active = true;
    let timer: number | undefined;
    let controller: AbortController | null = null;
    let requestId = 0;

    const refresh = async () => {
      if (!active || document.hidden) return;
      const currentRequest = ++requestId;
      controller?.abort();
      controller = new AbortController();
      try {
        const unread = await getPrivateMessageUnreadCount(controller.signal);
        if (active && currentRequest === requestId) setCount(unread);
      } catch {
        // Keep the last known badge when a refresh fails; inbox pages show errors.
      } finally {
        if (active && currentRequest === requestId && !document.hidden) {
          timer = window.setTimeout(() => void refresh(), REFRESH_MS);
        }
      }
    };
    const onVisibilityChange = () => {
      if (document.hidden) {
        window.clearTimeout(timer);
        controller?.abort();
      } else {
        void refresh();
      }
    };
    const onUnreadChange = () => void refresh();

    document.addEventListener('visibilitychange', onVisibilityChange);
    window.addEventListener('messages-unread-changed', onUnreadChange);
    void refresh();
    return () => {
      active = false;
      requestId += 1;
      window.clearTimeout(timer);
      controller?.abort();
      document.removeEventListener('visibilitychange', onVisibilityChange);
      window.removeEventListener('messages-unread-changed', onUnreadChange);
    };
  }, [userId]);

  return count;
}