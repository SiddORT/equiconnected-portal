import { Link } from 'react-router-dom';
import { useAuth } from '@/app/AuthContext';
import { Button } from '@/components/ui/Button';
import styles from './SignupPage.module.css';

export function ProviderAccountPage() {
  const { user, logout } = useAuth();

  async function handleLogout() {
    await logout();
  }

  return (
    <main className={styles.page}>
      <section className={styles.card} aria-labelledby="provider-account-heading">
        <header className={styles.header}>
          <Link className={styles.brand} to="/" aria-label="EquiConnected home">
            <img src="/logo.png" alt="" className={styles.logo} />
            <span><strong>EquiConnected</strong><small>Exceptional equine care</small></span>
          </Link>
          <p className={styles.eyebrow}>Provider account</p>
          <h1 id="provider-account-heading" className="text-display">Your provider account is approved.</h1>
        </header>
        <section className={styles.success}>
          <div className={styles.successMark} aria-hidden="true">✓</div>
          <p>
            Welcome, <strong>{user?.full_name ?? 'provider'}</strong>. Your directory listing has
            been staged for the EquiConnected team.
          </p>
          <p className={styles.muted}>
            Listing edits and publication are not available yet. We’ll let you know when provider
            account tools are ready.
          </p>
          <Button type="button" variant="secondary" onClick={() => void handleLogout()}>
            Sign out
          </Button>
        </section>
      </section>
    </main>
  );
}