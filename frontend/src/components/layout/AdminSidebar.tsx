/**
 * Admin portal sidebar navigation.
 * Extend this as new admin modules are added.
 */
import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '@/app/AuthContext';
import styles from './AdminSidebar.module.css';

interface NavItem {
  label: string;
  to: string;
  icon: string;
}

const NAV_ITEMS: NavItem[] = [
  { label: 'Dashboard', to: '/admin/dashboard', icon: '⊞' },
  // Future: { label: 'Hospitals', to: '/admin/hospitals', icon: '⊕' },
  // Future: { label: 'Users', to: '/admin/users', icon: '○' },
];

export function AdminSidebar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  async function handleLogout() {
    await logout();
    navigate('/admin/login');
  }

  return (
    <aside className={styles.sidebar} aria-label="Admin navigation">
      <div className={styles.brand}>
        <span className={styles.logoMark}>EC</span>
        <div className={styles.brandText}>
          <span className={styles.brandName}>EquiConnected</span>
          <span className={styles.brandRole}>Admin Portal</span>
        </div>
      </div>

      <nav className={styles.nav}>
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              [styles.navItem, isActive ? styles['navItem--active'] : ''].filter(Boolean).join(' ')
            }
          >
            <span className={styles.navIcon} aria-hidden="true">{item.icon}</span>
            <span>{item.label}</span>
          </NavLink>
        ))}
      </nav>

      <div className={styles.footer}>
        {user && (
          <div className={styles.userBlock}>
            <div className={styles.avatar} aria-hidden="true">
              {(user.first_name?.[0] ?? user.email[0]).toUpperCase()}
            </div>
            <div className={styles.userInfo}>
              <span className={styles.userName}>{user.full_name}</span>
              <span className={styles.userEmail}>{user.email}</span>
            </div>
          </div>
        )}
        <button onClick={handleLogout} className={styles.logoutBtn}>
          <span aria-hidden="true">⎋</span> Log out
        </button>
      </div>
    </aside>
  );
}
