import { Link, useLocation } from 'react-router-dom';
import styles from './LegalPage.module.css';

type LegalSection = {
  title: string;
  paragraphs?: string[];
  bullets?: string[];
};

type LegalPageContent = {
  label: string;
  title: string;
  updated: string;
  introduction: string;
  sections: LegalSection[];
};

const TERMS_CONTENT: LegalPageContent = {
  label: 'Legal',
  title: 'Terms of Service',
  updated: 'Updated August 21, 2026',
  introduction:
    'These Terms of Service (“Terms”) govern your access to and use of the EquiConnected platform, an online directory connecting horse owners in the United Arab Emirates with verified equine veterinarians and hospitals. By using EquiConnected, you agree to these Terms.',
  sections: [
    {
      title: 'Acceptance of Terms',
      paragraphs: [
        'By accessing or using EquiConnected, you confirm that you are at least 18 years old, capable of entering into a binding agreement, and that you accept these Terms and our Privacy Policy. If you do not agree, you must not use the platform.',
      ],
    },
    {
      title: 'The Service',
      paragraphs: [
        'EquiConnected is a directory and connection platform. We verify the licenses and credentials of listed veterinary professionals and facilities, but we do not provide veterinary services ourselves and are not a party to any engagement between horse owners and care providers.',
        'All veterinary advice, diagnosis, and treatment is provided directly by the relevant professional. In an emergency, always contact a veterinarian or emergency facility directly.',
      ],
    },
    {
      title: 'Accounts & Registration',
      bullets: [
        'You must provide accurate, current, and complete information when registering.',
        'You are responsible for safeguarding your account credentials and for all activity under your account.',
        'Professionals must hold, and maintain, all licenses required to practice in the UAE and must promptly update us if their status changes.',
        'We may suspend or terminate accounts that violate these Terms or applicable law.',
      ],
    },
    {
      title: 'Acceptable Use',
      paragraphs: ['When using EquiConnected, you agree not to:'],
      bullets: [
        'Provide false, misleading, or fraudulent information, including credentials or reviews;',
        'Use the platform for any unlawful purpose or in violation of UAE law;',
        'Harass, defame, or harm other users or professionals;',
        'Scrape, copy, or sell platform content or listings without our written consent;',
        'Interfere with the security or operation of the platform.',
      ],
    },
    {
      title: 'Content & Reviews',
      paragraphs: [
        'You retain ownership of content you submit (such as reviews and enquiries), and you grant EquiConnected a non-exclusive, worldwide, royalty-free license to use, display, and distribute that content in connection with operating the platform. You are responsible for ensuring your content is accurate, lawful, and does not infringe the rights of others. We may remove content that violates these Terms.',
      ],
    },
    {
      title: 'Intellectual Property',
      paragraphs: [
        'The EquiConnected name, logo, design, and all platform content (including user content) are owned by or licensed to EquiConnected and are protected by intellectual property laws. You may not use these without our prior written permission.',
      ],
    },
    {
      title: 'Disclaimers & Limitation of Liability',
      paragraphs: [
        'The platform is provided on an “as is” and “as available” basis. While we take care in verifying listed professionals, we make no warranty as to the quality, suitability, or outcome of any veterinary services obtained through the platform.',
        'To the maximum extent permitted by law, EquiConnected shall not be liable for any indirect, incidental, consequential, or special damages, or for any loss arising from services provided by third-party professionals, your use of or inability to use the platform, or unauthorised access to your data.',
      ],
    },
    {
      title: 'Termination',
      paragraphs: [
        'We may suspend or terminate your access to the platform at any time for breach of these Terms or where required by law. You may stop using the platform and request deletion of your account at any time. Provisions that by their nature should survive termination (including intellectual property, disclaimers, and limitation of liability) will survive.',
      ],
    },
    {
      title: 'Governing Law & Jurisdiction',
      paragraphs: [
        'These Terms are governed by the laws of the United Arab Emirates. Any dispute arising out of or in connection with the use of the platform shall be subject to the exclusive jurisdiction of the competent courts of the United Arab Emirates.',
      ],
    },
    {
      title: 'Changes to These Terms',
      paragraphs: [
        'We may revise these Terms from time to time. The updated version will be posted on this page with a revised effective date. Continued use of the platform after changes take effect constitutes acceptance of the revised Terms.',
      ],
    },
    {
      title: 'Contact Us',
      paragraphs: [
        'Questions about these Terms may be directed to legal@equiconnected.ae, EquiConnected, United Arab Emirates.',
      ],
    },
  ],
};

const PRIVACY_CONTENT: LegalPageContent = {
  label: 'Legal',
  title: 'Privacy Policy',
  updated: 'Updated August 21, 2026',
  introduction:
    'EquiConnected (“we”, “us”, “our”) operates an online directory connecting horse owners in the United Arab Emirates with verified equine veterinarians and hospitals. This Privacy Policy explains what information we collect, how we use it, and the choices available to you.',
  sections: [
    {
      title: 'Information We Collect',
      paragraphs: ['We collect information you provide directly to us, including:'],
      bullets: [
        'Account information — your name, email address, phone number, and location (provided when you create an account or join our launch list).',
        'Professional information — for veterinarians and hospitals, license details, credentials, specialisations, and practice information (provided when you apply).',
        'Communications — messages, enquiries, and reviews you submit through the platform.',
        'Usage data — page visits, searches performed, and device and browser information collected automatically when you use the site.',
      ],
    },
    {
      title: 'How We Use Your Information',
      paragraphs: ['We use the information we collect to:'],
      bullets: [
        'Provide, operate, and improve the EquiConnected platform;',
        'Verify the credentials of veterinary professionals and facilities;',
        'Connect horse owners with appropriate equine care providers;',
        'Send you service updates, launch notifications, and — with your consent — marketing communications;',
        'Respond to your enquiries and provide customer support;',
        'Detect, prevent, and address fraud, abuse, or security issues;',
        'Comply with applicable UAE laws and regulations.',
      ],
    },
    {
      title: 'Cookies & Similar Technologies',
      paragraphs: [
        'We use cookies and similar technologies to keep you signed in, remember your preferences, and understand how the platform is used. Essential cookies are required for the site to function; analytics cookies help improve the experience. You can control cookies through your browser settings, though disabling some may affect site functionality.',
      ],
    },
    {
      title: 'Sharing with Third Parties',
      paragraphs: ['We do not sell your personal information. We may share information with:'],
      bullets: [
        'Service providers who support our operations (hosting, analytics, email delivery), bound by confidentiality obligations;',
        'Veterinary professionals when you choose to contact or book with them through the platform;',
        'Legal authorities where required by UAE law, regulation, or valid legal process;',
        'Business successors in connection with a merger, acquisition, or sale of assets, subject to this policy.',
      ],
    },
    {
      title: 'Data Security & Retention',
      paragraphs: [
        'We apply appropriate technical and organisational measures to protect your information against unauthorised access, alteration, disclosure, or destruction. We retain your information only for as long as necessary to fulfil the purposes described in this policy or as required by applicable law.',
      ],
    },
    {
      title: 'Your Rights',
      paragraphs: [
        'Subject to applicable data protection law, including Federal Decree-Law No. 45 of 2021 on the Protection of Personal Data, you may:',
      ],
      bullets: [
        'Request access to the personal information we hold about you;',
        'Request correction of inaccurate or incomplete information;',
        'Request deletion of your personal information;',
        'Withdraw consent to marketing communications at any time;',
        'Object to or request restriction of certain processing.',
      ],
    },
    {
      title: 'Children’s Privacy',
      paragraphs: [
        'EquiConnected is not directed to individuals under the age of 18, and we do not knowingly collect personal information from children. If you believe a child has provided us with personal information, please contact us so we can remove it.',
      ],
    },
    {
      title: 'Changes to This Policy',
      paragraphs: [
        'We may update this Privacy Policy from time to time. We will post the revised version on this page and update the effective date above. Material changes will be communicated to registered users by email or in-app notice.',
      ],
    },
    {
      title: 'Contact Us',
      paragraphs: [
        'If you have questions about this Privacy Policy or our data practices, contact us at privacy@equiconnected.ae, EquiConnected, United Arab Emirates.',
      ],
    },
  ],
};

function LegalSection({ section, number }: { section: LegalSection; number: number }) {
  return (
    <section className={styles.section} aria-labelledby={`legal-section-${number}`}>
      <p className={styles.sectionNumber} aria-hidden="true">{String(number).padStart(2, '0')}</p>
      <div className={styles.sectionBody}>
        <h2 id={`legal-section-${number}`}>{section.title}</h2>
        {section.paragraphs?.map((paragraph) => <p key={paragraph}>{paragraph}</p>)}
        {section.bullets && (
          <ul>
            {section.bullets.map((bullet) => <li key={bullet}>{bullet}</li>)}
          </ul>
        )}
      </div>
    </section>
  );
}

export function LegalPage({ kind }: { kind: 'terms' | 'privacy' }) {
  const location = useLocation();
  const content = kind === 'terms' ? TERMS_CONTENT : PRIVACY_CONTENT;
  const otherPolicy = kind === 'terms'
    ? { label: 'Privacy Policy', to: '/privacy-policy' }
    : { label: 'Terms of Service', to: '/terms-of-service' };

  return (
    <div className={styles.page}>
      <header className={styles.masthead}>
        <div className={styles.mastheadInner}>
          <Link to="/" className={styles.brand} aria-label="EquiConnected home">
            <img src="/logo.png" alt="" />
            <span>EquiConnected</span>
          </Link>
          <Link to="/" className={styles.homeLink}>← Back to home</Link>
        </div>
        <div className={styles.titleBlock}>
          <p>{content.label}</p>
          <h1>{content.title}</h1>
          <time dateTime="2026-08-21">{content.updated}</time>
        </div>
      </header>

      <main className={styles.main} id="main-content">
        <div className={styles.content}>
          <p className={styles.introduction}>{content.introduction}</p>
          {content.sections.map((section, index) => (
            <LegalSection key={section.title} section={section} number={index + 1} />
          ))}
        </div>
      </main>

      <footer className={styles.footer}>
        <div className={styles.footerInner}>
          <p>© {new Date().getFullYear()} EquiConnected. All rights reserved.</p>
          <nav aria-label="Legal pages">
            <Link to={location.pathname === '/terms-of-service' ? '/privacy-policy' : '/terms-of-service'}>
              {otherPolicy.label}
            </Link>
            <Link to="/">Back to home</Link>
          </nav>
        </div>
      </footer>
    </div>
  );
}