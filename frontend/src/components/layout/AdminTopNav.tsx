import { useEffect, useRef, useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '@/app/AuthContext';
import styles from './AdminTopNav.module.css';

interface NavItem { label: string; to: string; icon: string; }
const NAV_ITEMS: NavItem[] = [
  { label: 'Dashboard', to: '/admin/dashboard', icon: '⊞' },
  // Add more nav items here as modules are built
];

export function AdminTopNav() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    }
    if (menuOpen) document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [menuOpen]);

  // Close dropdown on Escape
  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setMenuOpen(false);
    }
    if (menuOpen) document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [menuOpen]);

  async function handleLogout() {
    setMenuOpen(false);
    await logout();
    navigate('/admin/login');
  }

  const initials = user?.full_name
    ? user.full_name.split(' ').map((n) => n[0]).join('').slice(0, 2).toUpperCase()
    : user?.email?.[0]?.toUpperCase() ?? '?';

  return (
    <header className={styles.nav} role="banner">
      {/* ── Brand ─────────────────────────────────────── */}
      <div className={styles.brand}>
        <img src="/logo.png" alt="EquiConnected logo" className={styles.logoMark} />
        <div className={styles.brandText}>
          <span className={styles.brandName}>EquiConnected</span>
          <span className={styles.brandRole}>Admin Portal</span>
        </div>
      </div>

      {/* ── Nav links ─────────────────────────────────── */}
      <nav className={styles.links} aria-label="Admin navigation">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              [styles.link, isActive ? styles['link--active'] : ''].filter(Boolean).join(' ')
            }
          >
            <span className={styles.linkIcon} aria-hidden="true">{item.icon}</span>
            {item.label}
          </NavLink>
        ))}
      </nav>

      {/* ── Profile menu ──────────────────────────────── */}
      <div className={styles.profileArea} ref={menuRef}>
        <button
          className={styles.avatarBtn}
          aria-label="Open profile menu"
          aria-expanded={menuOpen}
          aria-haspopup="menu"
          onClick={() => setMenuOpen((o) => !o)}
        >
          <span className={styles.avatar} aria-hidden="true">{initials}</span>
          <span className={styles.chevron} aria-hidden="true">{menuOpen ? '▲' : '▼'}</span>
        </button>

        {menuOpen && (
          <div className={styles.dropdown} role="menu" aria-label="Profile options">
            {/* User info header */}
            <div className={styles.dropdownHeader}>
              <span className={styles.dropdownAvatar} aria-hidden="true">{initials}</span>
              <div className={styles.dropdownUserInfo}>
                <span className={styles.dropdownName}>{user?.full_name ?? 'Admin'}</span>
                <span className={styles.dropdownEmail}>{user?.email}</span>
              </div>
            </div>

            <div className={styles.dropdownDivider} />

            <button
              className={styles.dropdownItem}
              role="menuitem"
              onClick={() => setMenuOpen(false)}
            >
              <span aria-hidden="true">👤</span>
              Profile
            </button>

            <button
              className={styles.dropdownItem}
              role="menuitem"
              onClick={() => setMenuOpen(false)}
            >
              <span aria-hidden="true">⚙️</span>
              Settings
            </button>

            <div className={styles.dropdownDivider} />

            <button
              className={`${styles.dropdownItem} ${styles['dropdownItem--danger']}`}
              role="menuitem"
              onClick={handleLogout}
            >
              <span aria-hidden="true">↩</span>
              Logout
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
