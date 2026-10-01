import { Link } from 'react-router-dom';
import styles from './HomeV2.module.css';

export function HomeFooter({ member, careHref }: { member: boolean; careHref: string }) {
  return (
    <footer className={styles.footer} id="site-footer">
      <div className={styles.footerPitch}>
        <div>
          <span className={styles.footerSpark} aria-hidden="true">✦</span>
          <h2>A clearer way to find <em>equine care.</em></h2>
        </div>
        <div className={styles.footerPitchAside}>
          <p>Explore the services and locations providers share, then connect directly to ask about availability.</p>
          <div className={styles.footerCtas}>
            <Link to={careHref} className={styles.footerPrimary}>Find a provider <span aria-hidden="true">↗</span></Link>
            <Link to="/provider/signup" className={styles.footerSecondary}>List your practice</Link>
          </div>
        </div>
      </div>
      <div className={styles.footerMain}>
        <Link to="/" className={styles.footerBrand} aria-label="EquiConnected home">
          <img src="/equiconnected-logo.png" alt="" aria-hidden="true" />
        </Link>
        <nav className={styles.footerLinks} aria-label="Footer links">
          <div>
            <span>Platform</span>
            <Link to={careHref}>Find care</Link>
            <a href="/#owners">Owners &amp; riders</a>
            <a href="/#how-it-works">How it works</a>
            <a href="/#visiting">Visiting specialists</a>
            <a href="/#emergency">Emergency information</a>
          </div>
          <div>
            <span>For providers</span>
            <a href="/#providers">For providers</a>
            <Link to="/provider/signup">Join the network</Link>
            <Link to="/provider/login">Provider sign in</Link>
          </div>
          <div>
            <span>Company</span>
            <Link to="/about">About EquiConnected</Link>
            <a href="/#contact">Contact</a>
            <Link to="/privacy-policy">Privacy</Link>
            <Link to="/terms-of-service">Terms of service</Link>
          </div>
          <div>
            <span>Get in touch</span>
            <p>Questions about EquiConnected? Send us a message through the contact form.</p>
            <a href="/#contact" className={styles.footerContact}>Contact us <span aria-hidden="true">↗</span></a>
            {member ? <Link to="/profile">Your profile</Link> : <Link to="/login">Member sign in</Link>}
            <Link to={member ? '/providers' : '/signup'}>{member ? 'Provider directory' : 'Create an account'}</Link>
          </div>
        </nav>
      </div>
      <div className={styles.footerBottom}>
        <span>© {new Date().getFullYear()} EquiConnected</span>
        <span>Connecting the people who care for horses.</span>
      </div>
      <div className={styles.footerWordmark} aria-hidden="true">EquiConnected</div>
    </footer>
  );
}