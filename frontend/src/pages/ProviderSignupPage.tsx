/** Public registration page for hospitals, clinics, and doctors. */
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { extractErrorMessage, getApiErrorCode } from '@/api/client';
import * as authApi from '@/api/auth';
import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { LocationPicker } from '@/components/ui/LocationPicker';
import { PhoneInput } from '@/components/ui/PhoneInput';
import type {
  ProviderRegistrationRequest,
  ProviderType,
} from '@/types';
import { DEFAULT_COUNTRY } from '@/utils/countryCodes';
import styles from './SignupPage.module.css';

type FormErrors = Partial<Record<keyof ProviderRegistrationRequest, string>>;

const initialForm: ProviderRegistrationRequest = {
  first_name: '',
  last_name: '',
  email: '',
  mobile_number: '',
  country: '',
  state_province: '',
  city: '',
  password: '',
  password_confirmation: '',
  role: 'PROVIDER',
  provider_type: 'HOSPITAL',
  provider_name: '',
  visit_stability: 'STABLE_VISIT',
  professional_title: '',
  specialization_ids: [],
  years_experience: null,
  working_address: '',
  stable_visit: true,
  clinic_hospital_visit: false,
  maximum_working_radius_km: null,
  emergency_services_available: false,
  emergency_contact_number: null,
  accept_terms: false,
  accept_privacy: false,
};

const providerTypes: Array<{ value: ProviderType; label: string; description: string }> = [
  { value: 'HOSPITAL', label: 'Hospital', description: 'A hospital or referral centre.' },
  { value: 'CLINIC', label: 'Clinic', description: 'A clinic or care practice.' },
  { value: 'DOCTOR', label: 'Doctor / Vet', description: 'An independent equine professional.' },
];

export function validateProviderSignup(form: ProviderRegistrationRequest): FormErrors {
  const errors: FormErrors = {};
  for (const field of ['first_name', 'last_name', 'provider_name', 'mobile_number', 'country', 'city', 'professional_title', 'working_address'] as const) {
    if (!form[field].trim()) errors[field] = 'This field is required';
  }
  if (!form.specialization_ids.length) errors.specialization_ids = 'Select at least one specialization';
  if (form.years_experience === null || !Number.isInteger(form.years_experience)
    || form.years_experience < 0 || form.years_experience > 100) {
    errors.years_experience = 'Enter years of experience between 0 and 100';
  }
  if (form.stable_visit && (form.maximum_working_radius_km === null
    || !Number.isFinite(form.maximum_working_radius_km) || form.maximum_working_radius_km <= 0)) {
    errors.maximum_working_radius_km = 'Enter a working radius greater than 0 km';
  }
  if (form.emergency_services_available && !form.emergency_contact_number?.trim()) {
    errors.emergency_contact_number = 'Emergency contact number is required';
  } else if (form.emergency_services_available && !/^[0-9+\-()\s]{6,32}$/.test(form.emergency_contact_number?.trim() ?? '')) {
    errors.emergency_contact_number = 'Enter a valid emergency contact number';
  }
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

export function ProviderSignupPage() {
  const [form, setForm] = useState<ProviderRegistrationRequest>(initialForm);
  const [mobileCountry, setMobileCountry] = useState(DEFAULT_COUNTRY);
  const [errors, setErrors] = useState<FormErrors>({});
  const [globalError, setGlobalError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showPasswordConfirmation, setShowPasswordConfirmation] = useState(false);
  const [specializations, setSpecializations] = useState<Array<{ id: string; name: string }>>([]);
  const [specializationsError, setSpecializationsError] = useState<string | null>(null);
  const [loadingSpecializations, setLoadingSpecializations] = useState(true);

  useEffect(() => {
    let cancelled = false;
    authApi.listProviderSignupSpecializations()
      .then((items) => { if (!cancelled) setSpecializations(items); })
      .catch((error) => {
        if (!cancelled) setSpecializationsError(extractErrorMessage(error, 'Could not load specializations. Please refresh the page.'));
      })
      .finally(() => { if (!cancelled) setLoadingSpecializations(false); });
    return () => { cancelled = true; };
  }, []);

  function update<K extends keyof ProviderRegistrationRequest>(
    field: K,
    value: ProviderRegistrationRequest[K]
  ) {
    setForm((current) => ({
      ...current,
      [field]: value,
      ...(field === 'stable_visit' ? {
        visit_stability: value ? 'STABLE_VISIT' : 'NOT_STABLE_VISIT',
        maximum_working_radius_km: value ? current.maximum_working_radius_km : null,
      } : {}),
      ...(field === 'emergency_services_available' && !value ? { emergency_contact_number: null } : {}),
    }));
    setErrors((current) => ({
      ...current,
      [field]: undefined,
      ...(field === 'stable_visit' ? { maximum_working_radius_km: undefined } : {}),
      ...(field === 'emergency_services_available' ? { emergency_contact_number: undefined } : {}),
    }));
    setGlobalError(null);
  }

  function toggleSpecialization(id: string) {
    setForm((current) => ({
      ...current,
      specialization_ids: current.specialization_ids.includes(id)
        ? current.specialization_ids.filter((selectedId) => selectedId !== id)
        : [...current.specialization_ids, id],
    }));
    setErrors((current) => ({ ...current, specialization_ids: undefined }));
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    const nextErrors = validateProviderSignup(form);
    if (loadingSpecializations || specializationsError || !specializations.length) {
      setGlobalError(specializationsError ?? 'Specializations are unavailable. Please try again later.');
      return;
    }
    if (Object.keys(nextErrors).length) {
      setErrors(nextErrors);
      return;
    }
    setSubmitting(true);
    setGlobalError(null);
    try {
      await authApi.registerProvider({
        ...form,
        email: form.email.trim().toLowerCase(),
        mobile_number: `${mobileCountry.dialCode} ${form.mobile_number.trim()}`,
        country: form.country.trim(),
        state_province: form.state_province.trim(),
        city: form.city.trim(),
        provider_name: form.provider_name.trim(),
        professional_title: form.professional_title.trim(),
        working_address: form.working_address.trim(),
        emergency_contact_number: form.emergency_services_available
          ? form.emergency_contact_number?.trim() ?? null : null,
        maximum_working_radius_km: form.stable_visit ? form.maximum_working_radius_km : null,
      });
      setSubmitted(true);
    } catch (error) {
      setGlobalError(
        getApiErrorCode(error) === 'registration_unavailable'
          ? 'Provider registration is temporarily unavailable. Please try again later.'
          : extractErrorMessage(error, 'We could not submit your provider application. Please try again.')
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className={styles.page}>
      <section className={styles.card} aria-labelledby="provider-signup-heading">
        <header className={styles.header}>
          <Link className={styles.brand} to="/" aria-label="EquiConnected home">
            <img src="/logo.png" alt="" className={styles.logo} />
            <span><strong>EquiConnected</strong><small>Exceptional equine care</small></span>
          </Link>
          <p className={styles.eyebrow}>Provider registration</p>
          <h1 id="provider-signup-heading" className="text-display">Join as an equine care provider.</h1>
          <p className={styles.intro}>Create your account, verify your email, and we’ll review your application.</p>
        </header>

        {submitted ? (
          <section className={styles.success} aria-live="polite">
            <div className={styles.successMark} aria-hidden="true">✓</div>
            <h2 className="text-display">Check your inbox</h2>
            <p>We sent a secure verification link to <strong>{form.email}</strong>.</p>
            <p className={styles.muted}>After verification, your provider application will enter administrator review. The link expires in 24 hours.</p>
          </section>
        ) : (
          <form className={styles.form} onSubmit={handleSubmit} noValidate>
            {globalError && <Alert variant="error" onDismiss={() => setGlobalError(null)}>{globalError}</Alert>}
            <Input label="Provider or practice name" id="provider-signup-name" placeholder="e.g. Meadow Equine Clinic" containerClassName={styles.signupField} value={form.provider_name} onChange={(e) => update('provider_name', e.target.value)} error={errors.provider_name} disabled={submitting} required />
            <div className={styles.roleSection}>
              <span className={styles.roleLabel}>Provider type</span>
              <div className={styles.roleOptions}>
                {providerTypes.map((option) => (
                  <label className={`${styles.roleOption} ${form.provider_type === option.value ? styles.roleSelected : ''}`} key={option.value}>
                    <input type="radio" name="provider-type" value={option.value} checked={form.provider_type === option.value} onChange={() => update('provider_type', option.value)} disabled={submitting} />
                    <span><strong>{option.label}</strong><small>{option.description}</small></span>
                  </label>
                ))}
              </div>
            </div>
            <div className={styles.twoColumns}>
              <Input label="First name" id="provider-first-name" autoComplete="given-name" placeholder="e.g. Sarah" containerClassName={styles.signupField} value={form.first_name} onChange={(e) => update('first_name', e.target.value)} error={errors.first_name} disabled={submitting} required />
              <Input label="Last name" id="provider-last-name" autoComplete="family-name" placeholder="e.g. Williams" containerClassName={styles.signupField} value={form.last_name} onChange={(e) => update('last_name', e.target.value)} error={errors.last_name} disabled={submitting} required />
            </div>
            <Input label="Email address" type="email" id="provider-email" autoComplete="email" placeholder="you@example.com" containerClassName={styles.signupField} value={form.email} onChange={(e) => update('email', e.target.value)} error={errors.email} disabled={submitting} required />
            <div className={`${styles.signupField} ${styles.mobileField}`}>
              <span className={styles.mobileLabel}>Mobile number</span>
              <PhoneInput countryCode={mobileCountry.dialCode} isoCode={mobileCountry.code} number={form.mobile_number} onCountryChange={(dialCode, isoCode) => setMobileCountry({ ...mobileCountry, dialCode, code: isoCode })} onNumberChange={(number) => update('mobile_number', number)} error={errors.mobile_number} disabled={submitting} ariaLabel="Mobile number" />
            </div>
            <div className={styles.twoColumns}>
              <Input label="Professional title" id="provider-professional-title" maxLength={200} containerClassName={styles.signupField} value={form.professional_title} onChange={(e) => update('professional_title', e.target.value)} error={errors.professional_title} disabled={submitting} required />
              <Input label="Years of experience" id="provider-years-experience" type="number" min="0" max="100" step="1" containerClassName={styles.signupField} value={form.years_experience ?? ''} onChange={(e) => update('years_experience', e.target.value === '' ? null : Number(e.target.value))} error={errors.years_experience} disabled={submitting} required />
            </div>
            <div className={styles.roleSection}>
              <span className={styles.roleLabel} id="provider-specializations-label">Specializations *</span>
              {loadingSpecializations && <span className={styles.mobileLabel}>Loading specializations…</span>}
              {specializationsError && <p className={styles.consentError} role="alert">{specializationsError}</p>}
              {!loadingSpecializations && !specializationsError && specializations.length === 0 && (
                <p className={styles.consentError} role="alert">No specializations are available. Please try again later.</p>
              )}
              <div className={`${styles.roleOptions} ${styles.compactOptions}`} role="group" aria-labelledby="provider-specializations-label">
                {specializations.map((specialization) => (
                  <label className={`${styles.roleOption} ${styles.compactOption} ${form.specialization_ids.includes(specialization.id) ? styles.roleSelected : ''}`} key={specialization.id}>
                    <input type="checkbox" checked={form.specialization_ids.includes(specialization.id)} onChange={() => toggleSpecialization(specialization.id)} disabled={submitting} />
                    <span><strong>{specialization.name}</strong></span>
                  </label>
                ))}
              </div>
              {errors.specialization_ids && <p className={styles.consentError} role="alert">{errors.specialization_ids}</p>}
            </div>
            <LocationPicker value={form} onChange={(nextLocation) => { setForm((current) => ({ ...current, ...nextLocation })); setErrors((current) => ({ ...current, country: undefined, state_province: undefined, city: undefined })); setGlobalError(null); }} errors={{ country: errors.country, state_province: errors.state_province, city: errors.city }} disabled={submitting} theme="dark" required optionalState idPrefix="provider-signup-location" />
            <Input label="Working location / address" id="provider-working-address" maxLength={300} autoComplete="street-address" containerClassName={styles.signupField} value={form.working_address} onChange={(e) => update('working_address', e.target.value)} error={errors.working_address} disabled={submitting} required />
            <div className={styles.twoColumns}>
              {([
                { field: 'stable_visit', label: 'Stable visit' },
                { field: 'clinic_hospital_visit', label: 'Clinic/Hospital visit' },
              ] as const).map(({ field, label }) => (
                <div className={styles.roleSection} key={field}>
                  <span className={styles.roleLabel} id={`provider-${field}-label`}>{label}</span>
                  <div className={`${styles.roleOptions} ${styles.compactOptions}`} role="radiogroup" aria-labelledby={`provider-${field}-label`}>
                    {[true, false].map((option) => (
                      <label className={`${styles.roleOption} ${styles.compactOption} ${form[field] === option ? styles.roleSelected : ''}`} key={String(option)}>
                        <input type="radio" name={field} checked={form[field] === option} onChange={() => update(field, option)} disabled={submitting} />
                        <span><strong>{option ? 'Yes' : 'No'}</strong></span>
                      </label>
                    ))}
                  </div>
                </div>
              ))}
            </div>
            {form.stable_visit && (
              <Input label="Maximum Working Radius (KM)" id="provider-working-radius" type="number" min="0.1" step="any" containerClassName={styles.signupField} hint="Maximum distance from your working location for stable or home visits." value={form.maximum_working_radius_km ?? ''} onChange={(e) => update('maximum_working_radius_km', e.target.value === '' ? null : Number(e.target.value))} error={errors.maximum_working_radius_km} disabled={submitting} required />
            )}
            <div className={styles.roleSection}>
              <span className={styles.roleLabel} id="provider-emergency-label">Emergency services available</span>
              <div className={`${styles.roleOptions} ${styles.compactOptions}`} role="radiogroup" aria-labelledby="provider-emergency-label">
                {[true, false].map((option) => (
                  <label className={`${styles.roleOption} ${styles.compactOption} ${form.emergency_services_available === option ? styles.roleSelected : ''}`} key={String(option)}>
                    <input type="radio" name="emergency-services" checked={form.emergency_services_available === option} onChange={() => update('emergency_services_available', option)} disabled={submitting} />
                    <span><strong>{option ? 'Yes' : 'No'}</strong></span>
                  </label>
                ))}
              </div>
            </div>
            {form.emergency_services_available && (
              <Input label="Emergency contact number" id="provider-emergency-number" type="tel" autoComplete="tel" maxLength={32} containerClassName={styles.signupField} value={form.emergency_contact_number ?? ''} onChange={(e) => update('emergency_contact_number', e.target.value)} error={errors.emergency_contact_number} disabled={submitting} required />
            )}
            <div className={styles.twoColumns}>
              <Input label="Password" type={showPassword ? 'text' : 'password'} id="provider-password" autoComplete="new-password" placeholder="e.g. StableHorse7" containerClassName={styles.signupField} hint="At least 8 characters with upper- and lowercase letters and a number." value={form.password} onChange={(e) => update('password', e.target.value)} error={errors.password} disabled={submitting} required rightAdornment={<button type="button" className={styles.showHide} onClick={() => setShowPassword((visible) => !visible)} aria-label={showPassword ? 'Hide password' : 'Show password'} aria-pressed={showPassword}>{showPassword ? '🙈' : '👁'}</button>} />
              <Input label="Confirm password" type={showPasswordConfirmation ? 'text' : 'password'} id="provider-password-confirmation" autoComplete="new-password" placeholder="Repeat your password" containerClassName={styles.signupField} value={form.password_confirmation} onChange={(e) => update('password_confirmation', e.target.value)} error={errors.password_confirmation} disabled={submitting} required rightAdornment={<button type="button" className={styles.showHide} onClick={() => setShowPasswordConfirmation((visible) => !visible)} aria-label={showPasswordConfirmation ? 'Hide password confirmation' : 'Show password confirmation'} aria-pressed={showPasswordConfirmation}>{showPasswordConfirmation ? '🙈' : '👁'}</button>} />
            </div>
            <div className={styles.consents}>
              <div className={styles.consent}><input id="provider-accept-terms" type="checkbox" checked={form.accept_terms} onChange={(e) => update('accept_terms', e.target.checked)} disabled={submitting} /><label htmlFor="provider-accept-terms">I agree to the&nbsp;</label><Link to="/terms-of-service">Terms &amp; Conditions</Link><span>.</span></div>
              {errors.accept_terms && <p className={styles.consentError} role="alert">{errors.accept_terms}</p>}
              <div className={styles.consent}><input id="provider-accept-privacy" type="checkbox" checked={form.accept_privacy} onChange={(e) => update('accept_privacy', e.target.checked)} disabled={submitting} /><label htmlFor="provider-accept-privacy">I agree to the&nbsp;</label><Link to="/privacy-policy">Privacy Policy</Link><span>.</span></div>
              {errors.accept_privacy && <p className={styles.consentError} role="alert">{errors.accept_privacy}</p>}
            </div>
            <Button type="submit" variant="primary" size="lg" fullWidth loading={submitting}>
              {submitting ? 'Submitting application…' : 'Submit provider application'}
            </Button>
          </form>
        )}
      </section>
    </main>
  );
}