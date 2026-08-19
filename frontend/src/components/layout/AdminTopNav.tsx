import { useEffect, useRef, useState } from 'react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '@/app/AuthContext';
import styles from './AdminTopNav.module.css';

interface NavItem { label: string; to: string; icon: string; }
const NAV_ITEMS: NavItem[] = [
  { label: 'Dashboard', to: '/admin/dashboard', icon: '⊞' },
  { label: 'Doctors', to: '/admin/doctors', icon: '👨‍⚕️' },
];

const DIRECTORY_ITEMS: NavItem[] = [
  { label: 'Specializations', to: '/admin/specializations', icon: '⚕' },
  { label: 'Providers', to: '/admin/providers', icon: '🏥' },
  { label: 'Invitations', to: '/admin/invitations', icon: '✉' },
];

export function AdminTopNav() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  const [directoryOpen, setDirectoryOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const directoryRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
      if (directoryRef.current && !directoryRef.current.contains(e.target as Node)) {
        setDirectoryOpen(false);
      }
    }
    if (menuOpen || directoryOpen) document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [menuOpen, directoryOpen]);

  // Close dropdown on Escape
  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        setMenuOpen(false);
        setDirectoryOpen(false);
      }
    }
    if (menuOpen || directoryOpen) document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [menuOpen, directoryOpen]);

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
            aria-label={item.label}
            title={item.label}
            className={({ isActive }) =>
              [styles.link, isActive ? styles['link--active'] : ''].filter(Boolean).join(' ')
            }
          >
            <span className={styles.linkIcon} aria-hidden="true">{item.icon}</span>
            <span className={styles.linkLabel}>{item.label}</span>
          </NavLink>
        ))}

        <div className={styles.directoryMenu} ref={directoryRef}>
          <button
            type="button"
            className={[
              styles.link,
              styles.directoryTrigger,
              DIRECTORY_ITEMS.some((item) => location.pathname.startsWith(item.to))
                ? styles['link--active']
                : '',
            ].filter(Boolean).join(' ')}
            aria-haspopup="menu"
            aria-expanded={directoryOpen}
            aria-label="Directory Management"
            title="Directory Management"
            onClick={() => {
              setDirectoryOpen((open) => !open);
              setMenuOpen(false);
            }}
          >
            <span className={styles.linkIcon} aria-hidden="true">📂</span>
            <span className={styles.linkLabel}>Directory Management</span>
            <span className={styles.directoryChevron} aria-hidden="true">
              {directoryOpen ? '▲' : '▼'}
            </span>
          </button>

          {directoryOpen && (
            <div className={`${styles.dropdown} ${styles.directoryDropdown}`} role="menu" aria-label="Directory Management">
              {DIRECTORY_ITEMS.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  role="menuitem"
                  className={({ isActive }) =>
                    [
                      styles.dropdownNavItem,
                      isActive ? styles['dropdownNavItem--active'] : '',
                    ].filter(Boolean).join(' ')
                  }
                  onClick={() => setDirectoryOpen(false)}
                >
                  <span aria-hidden="true">{item.icon}</span>
                  {item.label}
                </NavLink>
              ))}
            </div>
          )}
        </div>
      </nav>

      {/* ── Profile menu ──────────────────────────────── */}
      <div className={styles.profileArea} ref={menuRef}>
        <button
          className={styles.avatarBtn}
          aria-label="Open profile menu"
          aria-expanded={menuOpen}
          aria-haspopup="menu"
          onClick={() => {
            setMenuOpen((o) => !o);
            setDirectoryOpen(false);
          }}
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
