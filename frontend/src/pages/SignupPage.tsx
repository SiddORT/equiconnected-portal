/**
 * Public registration page — /signup.
 * Creates an unverified account and prompts the user to activate it by email.
 */
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { extractErrorMessage } from '@/api/client';
import * as authApi from '@/api/auth';
import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { PhoneInput } from '@/components/ui/PhoneInput';
import type { PublicRoleSelection, RegistrationRequest } from '@/types';
import { DEFAULT_COUNTRY } from '@/utils/countryCodes';
import styles from './SignupPage.module.css';

type FormState = RegistrationRequest;
type FormErrors = Partial<Record<keyof FormState, string>>;

const initialForm: FormState = {
  first_name: '',
  last_name: '',
  email: '',
  mobile_number: '',
  country: '',
  city: '',
  password: '',
  password_confirmation: '',
  role: 'HORSE_OWNER',
  accept_terms: false,
  accept_privacy: false,
};

const roleOptions: Array<{ value: PublicRoleSelection; label: string; description: string }> = [
  { value: 'HORSE_OWNER', label: 'Horse Owner', description: 'I own or care for horses.' },
  { value: 'STABLE_MANAGER', label: 'Stable Manager', description: 'I manage a stable or yard.' },
  { value: 'BOTH', label: 'Both', description: 'Both descriptions apply to me.' },
];

function validate(form: FormState): FormErrors {
  const errors: FormErrors = {};
  const requiredFields: Array<keyof Pick<FormState, 'first_name' | 'last_name' | 'mobile_number' | 'country' | 'city'>> = [
    'first_name', 'last_name', 'mobile_number', 'country', 'city',
  ];
  requiredFields.forEach((field) => {
    if (!form[field].trim()) errors[field] = 'This field is required';
  });
  if (!form.email.trim()) errors.email = 'Email is required';
  else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) errors.email = 'Enter a valid email address';
  if (form.mobile_number.trim() && !/^[0-9+\-()\s]{6,32}$/.test(form.mobile_number.trim())) {
    errors.mobile_number = 'Enter a valid mobile number';
  }
  if (!form.password) errors.password = 'Password is required';
  else if (form.password.length < 8) errors.password = 'Use at least 8 characters';
  else if (!/[a-z]/.test(form.password) || !/[A-Z]/.test(form.password) || !/\d/.test(form.password)) {
    errors.password = 'Use upper- and lowercase letters plus a number';
  }
  if (!form.password_confirmation) errors.password_confirmation = 'Please confirm your password';
  else if (form.password !== form.password_confirmation) errors.password_confirmation = 'Passwords do not match';
  if (!form.accept_terms) errors.accept_terms = 'Please accept the Terms & Conditions';
  if (!form.accept_privacy) errors.accept_privacy = 'Please accept the Privacy Policy';
  return errors;
}

export function SignupPage() {
  const [form, setForm] = useState<FormState>(initialForm);
  const [mobileCountry, setMobileCountry] = useState(DEFAULT_COUNTRY);
  const [errors, setErrors] = useState<FormErrors>({});
  const [globalError, setGlobalError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showPasswordConfirmation, setShowPasswordConfirmation] = useState(false);

  function update<K extends keyof FormState>(field: K, value: FormState[K]) {
    setForm((current) => ({ ...current, [field]: value }));
    setErrors((current) => ({ ...current, [field]: undefined }));
    setGlobalError(null);
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    const nextErrors = validate(form);
    if (Object.keys(nextErrors).length) {
      setErrors(nextErrors);
      return;
    }

    setSubmitting(true);
    setGlobalError(null);
    try {
      await authApi.register({
        ...form,
        email: form.email.trim().toLowerCase(),
        mobile_number: `${mobileCountry.dialCode} ${form.mobile_number.trim()}`,
        country: form.country.trim(),
        city: form.city.trim(),
      });
      setSubmitted(true);
    } catch (error) {
      setGlobalError(extractErrorMessage(error, 'We could not create your account. Please try again.'));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className={styles.page}>
      <section className={styles.card} aria-labelledby="signup-heading">
        <header className={styles.header}>
          <Link className={styles.brand} to="/" aria-label="EquiConnected home">
            <img src="/logo.png" alt="" className={styles.logo} />
            <span>
              <strong>EquiConnected</strong>
              <small>Exceptional equine care</small>
            </span>
          </Link>
          <p className={styles.eyebrow}>Create your account</p>
          <h1 id="signup-heading" className="text-display">Join the EquiConnected community.</h1>
          <p className={styles.intro}>Connect with exceptional equine care from day one.</p>
        </header>

        {submitted ? (
          <section className={styles.success} aria-live="polite">
            <div className={styles.successMark} aria-hidden="true">✓</div>
            <h2 className="text-display">Check your inbox</h2>
            <p>
              We sent a secure verification link to <strong>{form.email}</strong>. Verify your
              email to activate your account.
            </p>
            <p className={styles.muted}>The link expires in 24 hours. If it is not in your inbox, check your spam folder.</p>
          </section>
        ) : (
          <form className={styles.form} onSubmit={handleSubmit} noValidate>
            {globalError && <Alert variant="error" onDismiss={() => setGlobalError(null)}>{globalError}</Alert>}

            <div className={styles.twoColumns}>
              <Input label="First name" id="signup-first-name" autoComplete="given-name" placeholder="e.g. Sarah" containerClassName={styles.signupField} value={form.first_name} onChange={(e) => update('first_name', e.target.value)} error={errors.first_name} disabled={submitting} required />
              <Input label="Last name" id="signup-last-name" autoComplete="family-name" placeholder="e.g. Williams" containerClassName={styles.signupField} value={form.last_name} onChange={(e) => update('last_name', e.target.value)} error={errors.last_name} disabled={submitting} required />
            </div>
            <Input label="Email address" type="email" id="signup-email" autoComplete="email" placeholder="you@example.com" containerClassName={styles.signupField} value={form.email} onChange={(e) => update('email', e.target.value)} error={errors.email} disabled={submitting} required />
            <div className={`${styles.signupField} ${styles.mobileField}`}>
              <span className={styles.mobileLabel}>Mobile number</span>
              <PhoneInput
                countryCode={mobileCountry.dialCode}
                isoCode={mobileCountry.code}
                number={form.mobile_number}
                onCountryChange={(dialCode, isoCode) => {
                  setMobileCountry({ ...mobileCountry, dialCode, code: isoCode });
                }}
                onNumberChange={(number) => update('mobile_number', number)}
                error={errors.mobile_number}
                disabled={submitting}
                ariaLabel="Mobile number"
              />
            </div>
            <div className={styles.twoColumns}>
              <Input label="Country" id="signup-country" autoComplete="country-name" placeholder="e.g. United Arab Emirates" containerClassName={styles.signupField} value={form.country} onChange={(e) => update('country', e.target.value)} error={errors.country} disabled={submitting} required />
              <Input label="City" id="signup-city" autoComplete="address-level2" placeholder="e.g. Dubai" containerClassName={styles.signupField} value={form.city} onChange={(e) => update('city', e.target.value)} error={errors.city} disabled={submitting} required />
            </div>
            <div className={styles.roleSection}>
              <span className={styles.roleLabel}>I am joining as</span>
              <div className={styles.roleOptions}>
                {roleOptions.map((option) => (
                  <label className={`${styles.roleOption} ${form.role === option.value ? styles.roleSelected : ''}`} key={option.value}>
                    <input type="radio" name="signup-role" value={option.value} checked={form.role === option.value} onChange={() => update('role', option.value)} disabled={submitting} />
                    <span><strong>{option.label}</strong><small>{option.description}</small></span>
                  </label>
                ))}
              </div>
            </div>
            <div className={styles.twoColumns}>
              <Input
                label="Password"
                type={showPassword ? 'text' : 'password'}
                id="signup-password"
                autoComplete="new-password"
                placeholder="e.g. StableHorse7"
                containerClassName={styles.signupField}
                hint="At least 8 characters with upper- and lowercase letters and a number."
                value={form.password}
                onChange={(e) => update('password', e.target.value)}
                error={errors.password}
                disabled={submitting}
                required
                rightAdornment={
                  <button
                    type="button"
                    className={styles.showHide}
                    onClick={() => setShowPassword((visible) => !visible)}
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                    aria-pressed={showPassword}
                  >
                    {showPassword ? '🙈' : '👁'}
                  </button>
                }
              />
              <Input
                label="Confirm password"
                type={showPasswordConfirmation ? 'text' : 'password'}
                id="signup-password-confirmation"
                autoComplete="new-password"
                placeholder="Repeat your password"
                containerClassName={styles.signupField}
                value={form.password_confirmation}
                onChange={(e) => update('password_confirmation', e.target.value)}
                error={errors.password_confirmation}
                disabled={submitting}
                required
                rightAdornment={
                  <button
                    type="button"
                    className={styles.showHide}
                    onClick={() => setShowPasswordConfirmation((visible) => !visible)}
                    aria-label={showPasswordConfirmation ? 'Hide password confirmation' : 'Show password confirmation'}
                    aria-pressed={showPasswordConfirmation}
                  >
                    {showPasswordConfirmation ? '🙈' : '👁'}
                  </button>
                }
              />
            </div>
            <div className={styles.consents}>
              <div className={styles.consent}>
                <input id="accept-terms" type="checkbox" checked={form.accept_terms} onChange={(e) => update('accept_terms', e.target.checked)} disabled={submitting} />
                <label htmlFor="accept-terms">I agree to the&nbsp;</label>
                <Link to="/terms-of-service">Terms &amp; Conditions</Link>
                <span>.</span>
              </div>
              {errors.accept_terms && <p className={styles.consentError} role="alert">{errors.accept_terms}</p>}
              <div className={styles.consent}>
                <input id="accept-privacy" type="checkbox" checked={form.accept_privacy} onChange={(e) => update('accept_privacy', e.target.checked)} disabled={submitting} />
                <label htmlFor="accept-privacy">I agree to the&nbsp;</label>
                <Link to="/privacy-policy">Privacy Policy</Link>
                <span>.</span>
              </div>
              {errors.accept_privacy && <p className={styles.consentError} role="alert">{errors.accept_privacy}</p>}
            </div>
            <Button type="submit" variant="primary" size="lg" fullWidth loading={submitting}>
              {submitting ? 'Creating account…' : 'Create account'}
            </Button>
          </form>
        )}
      </section>
    </main>
  );
}
