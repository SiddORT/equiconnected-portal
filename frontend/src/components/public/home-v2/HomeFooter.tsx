import { Link } from 'react-router-dom';
import styles from '@/pages/PublicPage.module.css';

export function HomeFooter({ member, careHref }: { member: boolean; careHref: string }) {
  return (
    <footer className={styles.footer}>
      <div className={styles.footerTop}>
        <Link to="/" className={styles.footerBrand} aria-label="EquiConnected home">
          <img src="/equiconnected-logo.png" alt="" aria-hidden="true" />
        </Link>
        <p>For every horse, and everyone who cares for them.</p>
      </div>
      <div className={styles.footerLinks}>
        <div>
          <span>Explore</span>
          <Link to={careHref}>Find care</Link>
          <a href="/#owners">Owners &amp; stable teams</a>
        </div>
        <div>
          <span>For providers</span>
          <Link to="/provider/signup">Join the network</Link>
          <Link to="/provider/login">Provider sign in</Link>
        </div>
        <div>
          <span>Your account</span>
          {member ? <Link to="/profile">Your profile</Link> : <Link to="/login">Member sign in</Link>}
          <Link to={member ? '/providers' : '/signup'}>{member ? 'Provider directory' : 'Create an account'}</Link>
        </div>
        <div>
          <span>About</span>
          <Link to="/privacy-policy">Privacy</Link>
          <Link to="/terms-of-service">Terms of service</Link>
          <Link to="/admin/login">Admin login</Link>
        </div>
      </div>
      <div className={styles.footerBottom}>
        <span>© {new Date().getFullYear()} EquiConnected</span>
        <span>Made for better equine care connections.</span>
      </div>
    </footer>
  );
}