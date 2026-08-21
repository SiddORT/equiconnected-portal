import { useState } from 'react';
import { Link, NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '@/app/AuthContext';
import styles from './MemberTopNav.module.css';

export function MemberTopNav() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [loggingOut, setLoggingOut] = useState(false);

  async function handleLogout() {
    setLoggingOut(true);
    try {
      await logout();
    } finally {
      navigate('/login', { replace: true });
    }
  }

  return (
    <header className={styles.nav} role="banner">
      <div className={styles.inner}>
        <Link className={styles.brand} to="/" aria-label="EquiConnected home">
          <img src="/logo.png" alt="" className={styles.logo} />
          <span>
            <strong>EquiConnected</strong>
            <small>Member area</small>
          </span>
        </Link>

        <nav className={styles.links} aria-label="Member navigation">
          <NavLink
            to="/providers"
            className={({ isActive }) => `${styles.link} ${isActive ? styles.active : ''}`}
          >
            Browse providers
          </NavLink>
          <NavLink
            to="/profile"
            className={({ isActive }) => `${styles.link} ${isActive ? styles.active : ''}`}
          >
            Your profile
          </NavLink>
        </nav>

        <div className={styles.account}>
          <span className={styles.name}>{user?.full_name ?? user?.email}</span>
          <button
            type="button"
            className={styles.logout}
            onClick={handleLogout}
            disabled={loggingOut}
          >
            <span aria-hidden="true">↩</span>
            {loggingOut ? 'Logging out…' : 'Log out'}
          </button>
        </div>
      </div>
    </header>
  );
}