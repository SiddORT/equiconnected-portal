import { useState } from 'react';
import { Link, NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '@/app/AuthContext';
import { useMessageUnreadCount } from '@/components/messaging/useMessageUnreadCount';
import styles from './ProviderTopNav.module.css';

function formatProviderDisplayName(fullName?: string | null, email?: string | null) {
  const name = fullName?.trim();
  if (name) return name;
  return email?.trim() || 'Provider';
}

export function ProviderTopNav() {
  const { user, logout } = useAuth();
  const unreadMessages = useMessageUnreadCount(user?.id);
  const navigate = useNavigate();
  const [loggingOut, setLoggingOut] = useState(false);
  const displayName = formatProviderDisplayName(user?.full_name, user?.email);

  async function handleLogout() {
    if (loggingOut) return;
    setLoggingOut(true);
    try {
      await logout();
    } catch {
      // AuthContext clears the local session in its finally block; still return
      // the provider to sign in if the server-side logout request fails.
    } finally {
      navigate('/provider/login', { replace: true });
    }
  }

  return (
    <header className={styles.nav} role="banner">
      <div className={styles.inner}>
        <Link className={styles.brand} to="/" aria-label="EquiConnected home">
          <img src="/logo.png" alt="" className={styles.logo} />
          <span>
            <strong>EquiConnected</strong>
            <small>Provider portal</small>
          </span>
        </Link>

        <nav className={styles.links} aria-label="Provider navigation">
          <NavLink to="/provider/account" className={({ isActive }) => `${styles.link} ${isActive ? styles.active : ''}`}>Account</NavLink>
          <NavLink to="/provider/insights" className={({ isActive }) => `${styles.link} ${isActive ? styles.active : ''}`}>Insights</NavLink>
          <NavLink to="/provider/messages" className={({ isActive }) => `${styles.link} ${isActive ? styles.active : ''}`}>
            Messages{unreadMessages > 0 && <span className={styles.unreadBadge} aria-label={`${unreadMessages} unread messages`}>{unreadMessages > 99 ? '99+' : unreadMessages}</span>}
          </NavLink>
        </nav>

        <div className={styles.account}>
          <span className={styles.welcome}>
            Welcome, <strong>{displayName}</strong>
          </span>
          <button
            type="button"
            className={styles.logout}
            onClick={() => void handleLogout()}
            disabled={loggingOut}
          >
            <span aria-hidden="true">↩</span>
            {loggingOut ? 'Logging out…' : 'Logout'}
          </button>
        </div>
      </div>
    </header>
  );
}