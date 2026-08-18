/**
 * Admin portal layout shell — sidebar + main content area.
 * Sidebar is rendered here so DashboardPage doesn't need to include it.
 */
import { Outlet } from 'react-router-dom';
import styles from './AdminLayout.module.css';

export function AdminLayout() {
  return (
    <div className={styles.shell}>
      <main className={styles.main} id="main-content">
        <Outlet />
      </main>
    </div>
  );
}
