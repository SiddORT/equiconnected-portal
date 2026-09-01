import { Link } from 'react-router-dom';
import styles from './Footer.module.css';

export function Footer() {
  const year = new Date().getFullYear();
  return (
    <footer id="site-footer" className={styles.footer} role="contentinfo">
      <div className={`container ${styles.inner}`}>
        <div className={styles.footerTop}>
          <Link to="/" className={styles.brand} aria-label="EquiConnected home">
            <span className={styles.logoMark} aria-hidden="true">EC</span>
            <span className={styles.logoText}>EquiConnected</span>
          </Link>
          <p className={styles.tagline}>A clearer path to the right care.</p>
        </div>

        <nav aria-label="Footer navigation" className={styles.navigation}>
          <FooterGroup title="Member" links={[
            { label: 'Find care', to: '/signup' },
            { label: 'Specializations', to: '/#specializations' },
            { label: 'Care near you', to: '/#care-near-you' },
          ]} />
          <FooterGroup title="Provider" links={[
            { label: 'Join as a provider', to: '/provider/signup' },
            { label: 'Doctors', to: '/#care-near-you' },
            { label: 'Clinics', to: '/#care-near-you' },
            { label: 'Hospitals', to: '/#care-near-you' },
          ]} />
          <FooterGroup title="Company" links={[
            { label: 'Why EquiConnected', to: '/#why-equiconnected' },
            { label: 'How it works', to: '/#how-it-works' },
            { label: 'Privacy', to: '/privacy-policy' },
            { label: 'Terms', to: '/terms-of-service' },
          ]} />
          <FooterGroup title="Account" links={[
            { label: 'Member login', to: '/login' },
            { label: 'Provider login', to: '/provider/login' },
            { label: 'Admin login', to: '/admin/login' },
          ]} />
        </nav>

        <p className={styles.copy}>
          © {year} EquiConnected. All rights reserved.
        </p>
      </div>
    </footer>
  );
}

type FooterLink = {
  label: string;
  to: string;
};

function FooterGroup({ title, links }: { title: string; links: FooterLink[] }) {
  return (
    <div className={styles.group}>
      <h2 className={styles.groupTitle}>{title}</h2>
      <ul className={styles.linkList}>
        {links.map((link) => (
          <li key={link.label}>
            {link.to.startsWith('/#') ? (
              <a href={link.to} className={styles.link}>{link.label}</a>
            ) : (
              <Link to={link.to} className={styles.link}>{link.label}</Link>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
