/**
 * SubmissionSuccessPage — static confirmation shown after an invitation
 * submission. Route: /provider/invite/success (public).
 */
import styles from './SubmissionSuccessPage.module.css';

export function SubmissionSuccessPage() {
  return (
    <div className={styles.page}>
      <main className={styles.card} role="status">
        <span className={styles.icon} aria-hidden="true">✅</span>
        <span className={styles.brand}>EquiConnected</span>
        <h1 className={styles.title}>Submission received</h1>
        <p className={styles.text}>
          Thank you — your profile has been submitted and is now under review by our admin
          team. We'll review your details and any organization associations you requested.
        </p>
        <p className={styles.text}>
          You'll be contacted by email once the review is complete. You can safely close
          this page.
        </p>
      </main>
    </div>
  );
}
