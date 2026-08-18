import { Outlet } from 'react-router-dom';
import { AdminTopNav } from './AdminTopNav';
import styles from './AdminLayout.module.css';

export function AdminLayout() {
  return (
    <div className={styles.shell}>
      <AdminTopNav />
      <main className={styles.main} id="main-content">
        <Outlet />
      </main>
    </div>
  );
}
