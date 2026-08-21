import { Outlet } from 'react-router-dom';
import { MemberTopNav } from './MemberTopNav';
import styles from './MemberLayout.module.css';

export function MemberLayout() {
  return (
    <div className={styles.shell}>
      <MemberTopNav />
      <Outlet />
    </div>
  );
}