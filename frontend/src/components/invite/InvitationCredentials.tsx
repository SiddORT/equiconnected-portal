import { useState } from 'react';
import { Card } from '@/components/ui/Card';
import { Input } from '@/components/ui/Input';
import styles from './InvitationCredentials.module.css';

export function validateInvitationCredentials(password: string, confirmation: string): Record<string, string> {
  const errors: Record<string, string> = {};
  if (password.length < 8 || password.length > 128 ||
      !/[a-z]/.test(password) || !/[A-Z]/.test(password) || !/\d/.test(password)) {
    errors.password = 'Use 8–128 characters with upper- and lowercase letters and a number.';
  }
  if (password !== confirmation) errors.password_confirmation = 'Passwords do not match.';
  return errors;
}

interface InvitationCredentialsProps {
  recipientEmail: string;
  password: string;
  confirmation: string;
  onPasswordChange: (value: string) => void;
  onConfirmationChange: (value: string) => void;
  errors?: Record<string, string>;
  disabled?: boolean;
}

/** Invitation-only account credentials; values are held in memory and never included in drafts. */
export function InvitationCredentials({
  recipientEmail,
  password,
  confirmation,
  onPasswordChange,
  onConfirmationChange,
  errors = {},
  disabled = false,
}: InvitationCredentialsProps) {
  const [passwordVisible, setPasswordVisible] = useState(false);
  const [confirmationVisible, setConfirmationVisible] = useState(false);

  return (
    <Card padding="lg" shadow="sm">
      <section className={styles.section} aria-labelledby="invitation-credentials-heading">
        <h3 id="invitation-credentials-heading" className={styles.title}>Provider portal account</h3>
        <p className={styles.note}>
          Your login email is <strong>{recipientEmail}</strong>. This is separate from the public
          contact emails on your provider profile. Choose a password now; your account will be
          available after administrator approval.
        </p>
        <p className={styles.note}>Passwords are not saved in profile drafts; enter them again before final submission.</p>
        <div className={styles.fields}>
          <Input
            label="Password"
            id="invitation-password"
            type={passwordVisible ? 'text' : 'password'}
            autoComplete="new-password"
            value={password}
            onChange={(event) => onPasswordChange(event.target.value)}
            error={errors.password}
            disabled={disabled}
            hint="Use 8–128 characters with upper- and lowercase letters and a number."
            rightAdornment={
              <button
                type="button"
                className={styles.visibilityToggle}
                aria-label={passwordVisible ? 'Hide password' : 'Show password'}
                aria-pressed={passwordVisible}
                onClick={() => setPasswordVisible((visible) => !visible)}
              >
                {passwordVisible ? 'Hide' : 'Show'}
              </button>
            }
            required
          />
          <Input
            label="Confirm password"
            id="invitation-password-confirmation"
            type={confirmationVisible ? 'text' : 'password'}
            autoComplete="new-password"
            value={confirmation}
            onChange={(event) => onConfirmationChange(event.target.value)}
            error={errors.password_confirmation}
            disabled={disabled}
            rightAdornment={
              <button
                type="button"
                className={styles.visibilityToggle}
                aria-label={confirmationVisible ? 'Hide confirmation' : 'Show confirmation'}
                aria-pressed={confirmationVisible}
                onClick={() => setConfirmationVisible((visible) => !visible)}
              >
                {confirmationVisible ? 'Hide' : 'Show'}
              </button>
            }
            required
          />
        </div>
      </section>
    </Card>
  );
}