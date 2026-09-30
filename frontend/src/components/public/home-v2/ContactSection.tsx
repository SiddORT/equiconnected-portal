import { useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { extractErrorMessage } from '@/api/client';
import { sendContactMessage, type ContactMessageRequest } from '@/api/public';
import { CountryCombobox } from '@/components/ui/CountryCombobox';
import { DEFAULT_COUNTRY, findByIsoCode } from '@/utils/countryCodes';
import styles from './ContactSection.module.css';

export function ContactSection() {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [enquiryType, setEnquiryType] = useState<ContactMessageRequest['enquiry_type']>('general');
  const [country, setCountry] = useState(findByIsoCode('AE') ?? DEFAULT_COUNTRY);
  const [phone, setPhone] = useState('');
  const [message, setMessage] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState('');

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting) return;
    setError('');
    setSubmitting(true);
    try {
      await sendContactMessage({
        name: name.trim(),
        email: email.trim(),
        enquiry_type: enquiryType,
        ...(phone.trim() ? { phone: `${country.dialCode} ${phone.trim()}` } : {}),
        message: message.trim(),
      });
      setSubmitted(true);
    } catch (cause) {
      setError(extractErrorMessage(cause, 'We could not send your message. Please try again later.'));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className={styles.section} id="contact" aria-labelledby="contact-heading">
      <div className={styles.visual}>
        <img src="/home-v2-hero.jpg" alt="" loading="lazy" />
        <div className={styles.visualContent}>
          <p className={styles.kicker}><span aria-hidden="true" />Contact us</p>
          <h2 id="contact-heading">Let’s talk<br /> <em>horses.</em></h2>
          <div className={styles.topics} aria-label="What you can ask us about">
            <p><strong>For horse owners</strong>Questions about the platform</p>
            <p><strong>For providers</strong>Listing your practice</p>
            <p><strong>For partners</strong>Working together</p>
          </div>
        </div>
        <span className={styles.credit}>Photo by Helena Lopes on Unsplash</span>
      </div>
      <div className={styles.formSide}>
        <div className={styles.formInner}>
          <p className={styles.formLead}>Questions about the platform, listing your practice or partnering with us? <span>Send us a message and we’ll reply by email.</span></p>
          {submitted ? (
            <div className={styles.confirmation} role="status">
              <h3>Thank you for reaching out.</h3>
              <p>Your message has been submitted. We’ll respond by email when we can.</p>
            </div>
          ) : (
            <form className={styles.form} onSubmit={(event) => void handleSubmit(event)} aria-label="Contact EquiConnected">
              <div className={styles.fields}>
                <label className={styles.field}>
                  <span>Full name</span>
                  <input type="text" name="name" autoComplete="name" placeholder="Your name" value={name} onChange={(event) => setName(event.target.value)} minLength={2} maxLength={120} required disabled={submitting} />
                </label>
                <label className={styles.field}>
                  <span>Email</span>
                  <input type="email" name="email" autoComplete="email" placeholder="you@example.com" value={email} onChange={(event) => setEmail(event.target.value)} required disabled={submitting} />
                </label>
                <label className={styles.field}>
                  <span>Enquiry type</span>
                  <select name="enquiry_type" value={enquiryType} onChange={(event) => setEnquiryType(event.target.value as ContactMessageRequest['enquiry_type'])} disabled={submitting}>
                    <option value="general">General enquiry</option>
                    <option value="listing">Listing my practice</option>
                    <option value="partnership">Partnership</option>
                    <option value="other">Other</option>
                  </select>
                </label>
                <div className={styles.field}>
                  <label htmlFor="contact-phone">Phone <small>· optional</small></label>
                  <div className={styles.phoneRow}>
                    <CountryCombobox value={country} onChange={setCountry} disabled={submitting} />
                    <input id="contact-phone" type="tel" name="phone" autoComplete="tel-national" placeholder="50 123 4567" value={phone} onChange={(event) => setPhone(event.target.value)} maxLength={25} disabled={submitting} />
                  </div>
                </div>
                <label className={`${styles.field} ${styles.messageField}`}>
                  <span>Message</span>
                  <textarea name="message" placeholder="How can we help?" value={message} onChange={(event) => setMessage(event.target.value)} minLength={10} maxLength={4000} required disabled={submitting} />
                </label>
              </div>
              {error && <p className={styles.error} role="alert">{error}</p>}
              <div className={styles.formBottom}>
                <p>Your details are used to respond to your enquiry. <Link to="/privacy-policy">Privacy Policy</Link></p>
                <button type="submit" disabled={submitting}>{submitting ? 'Sending…' : 'Send message'} <span aria-hidden="true">↗</span></button>
              </div>
            </form>
          )}
        </div>
      </div>
    </section>
  );
}