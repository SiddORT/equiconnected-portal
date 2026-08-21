import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '@/app/AuthContext';
import { extractErrorMessage, getApiErrorCode } from '@/api/client';
import * as providersApi from '@/api/providers';
import { useTimeSettings } from '@/app/TimeSettingsContext';
import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { ProviderTopNav } from '@/components/layout/ProviderTopNav';
import { ReviewCardList } from '@/components/reviews/ReviewCard';
import type { ProviderPortalProfile, ProviderPortalUpdate, ProviderSpecializationBrief } from '@/types';
import styles from './ProviderAccountPage.module.css';

type Notice = { variant: 'success' | 'error'; text: string } | null;

function formattedList(value: unknown) {
  return JSON.stringify(value, null, 2);
}

export function ProviderAccountPage() {
  const { user, logout } = useAuth();
  const { formatTimestamp } = useTimeSettings();
  const [profile, setProfile] = useState<ProviderPortalProfile | null>(null);
  const [specializations, setSpecializations] = useState<ProviderSpecializationBrief[]>([]);
  const [form, setForm] = useState<ProviderPortalUpdate>({});
  const [locations, setLocations] = useState('[]');
  const [phones, setPhones] = useState('[]');
  const [emails, setEmails] = useState('[]');
  const [photos, setPhotos] = useState('[]');
  const [qualifications, setQualifications] = useState('[]');
  const [loading, setLoading] = useState(true);
  const [legacyApprovedAccount, setLegacyApprovedAccount] = useState(false);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState<Notice>(null);
  const [feedbackOpen, setFeedbackOpen] = useState(false);
  const feedbackTriggerRef = useRef<HTMLButtonElement>(null);
  const feedbackCloseRef = useRef<HTMLButtonElement>(null);
  const feedbackWasOpen = useRef(false);

  function populate(next: ProviderPortalProfile) {
    setProfile(next);
    const editable = next.editable_profile;
    setForm({
      name: editable.name,
      description: editable.description,
      email: editable.email,
      phone: editable.phone,
      website: editable.website,
      visit_stability: editable.visit_stability,
      specialization_ids: editable.specialization_ids,
      professional_title: editable.professional_title ?? null,
      biography: editable.biography ?? null,
      years_experience: editable.years_experience ?? null,
      experience_description: editable.experience_description ?? null,
    });
    setLocations(formattedList(editable.locations));
    setPhones(formattedList(editable.phones));
    setEmails(formattedList(editable.emails));
    setPhotos(formattedList(editable.photos));
    setQualifications(formattedList(editable.qualifications));
  }

  useEffect(() => {
    void (async () => {
      try {
        const [next, choices] = await Promise.all([
          providersApi.getProviderPortalProfile(),
          providersApi.getProviderPortalSpecializations(),
        ]);
        populate(next);
        setSpecializations(choices);
      } catch (err) {
        if (getApiErrorCode(err) === 'provider_portal_unavailable') {
          // Approved self-service provider accounts continue to use this route,
          // but are deliberately outside the invitation-owned portal boundary.
          setLegacyApprovedAccount(true);
        } else {
          setNotice({ variant: 'error', text: extractErrorMessage(err, 'Your provider portal could not be loaded.') });
        }
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  function update<K extends keyof ProviderPortalUpdate>(field: K, value: ProviderPortalUpdate[K]) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  function parseList(label: string, value: string) {
    try {
      const parsed: unknown = JSON.parse(value);
      if (!Array.isArray(parsed)) throw new Error();
      return parsed;
    } catch {
      throw new Error(`${label} must be a valid JSON list.`);
    }
  }

  async function save(event: React.FormEvent) {
    event.preventDefault();
    try {
      const body: ProviderPortalUpdate = {
        ...form,
        locations: parseList('Locations', locations) as ProviderPortalUpdate['locations'],
        phones: parseList('Phone contacts', phones) as ProviderPortalUpdate['phones'],
        emails: parseList('Email contacts', emails) as ProviderPortalUpdate['emails'],
        photos: parseList('Photos', photos) as ProviderPortalUpdate['photos'],
      };
      if (profile?.doctor_fields_available) {
        body.qualifications = parseList('Qualifications', qualifications) as ProviderPortalUpdate['qualifications'];
      } else {
        delete body.professional_title;
        delete body.biography;
        delete body.years_experience;
        delete body.experience_description;
      }
      setSaving(true);
      setNotice(null);
      const updated = await providersApi.updateProviderPortalProfile(body);
      populate(updated);
      setNotice({
        variant: 'success',
        text: updated.profile_update?.review_status === 'PENDING_REVIEW'
          ? 'Your proposed profile update is awaiting administrator review. Your live listing is unchanged until approval.'
          : 'Your unpublished provider profile has been saved.',
      });
    } catch (err) {
      setNotice({ variant: 'error', text: err instanceof Error ? err.message : extractErrorMessage(err, 'Your profile could not be saved.') });
    } finally {
      setSaving(false);
    }
  }

  async function discardDraft() {
    try {
      setSaving(true);
      setNotice(null);
      populate(await providersApi.discardProviderPortalProfileUpdate());
      setNotice({
        variant: 'success',
        text: 'Your draft was discarded and the latest approved listing has been reloaded. You can make a new proposal when ready.',
      });
    } catch (err) {
      setNotice({ variant: 'error', text: extractErrorMessage(err, 'Your draft could not be discarded.') });
    } finally {
      setSaving(false);
    }
  }

  useEffect(() => {
    if (feedbackOpen) {
      feedbackWasOpen.current = true;
      feedbackCloseRef.current?.focus();
      return;
    }
    if (feedbackWasOpen.current) {
      feedbackWasOpen.current = false;
      feedbackTriggerRef.current?.focus();
    }
  }, [feedbackOpen]);

  useEffect(() => {
    if (!feedbackOpen) return;

    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        event.preventDefault();
        setFeedbackOpen(false);
      }
    }

    document.addEventListener('keydown', closeOnEscape);
    return () => document.removeEventListener('keydown', closeOnEscape);
  }, [feedbackOpen]);

  if (loading) {
    return (
      <div className={styles.page}>
        <ProviderTopNav />
        <main className={styles.state}><div className={styles.loading} role="status"><LoadingSpinner /> Loading your provider portal…</div></main>
      </div>
    );
  }
  if (!profile) {
    if (legacyApprovedAccount) {
      return (
        <div className={styles.page}>
          <ProviderTopNav />
          <main className={styles.state}><section className={styles.card}>
            <p className={styles.eyebrow}>Provider account</p>
            <h1 className="text-display">Your provider account is approved.</h1>
            <p className={styles.empty}>
              Welcome, {user?.full_name ?? 'provider'}. Your directory listing is staged for the EquiConnected team.
            </p>
            <p className={styles.hint}>
              Profile editing is currently available through administrator review. We’ll let you know when more account tools are ready.
            </p>
            <Button type="button" variant="secondary" onClick={() => void logout()}>Sign out</Button>
          </section></main>
        </div>
      );
    }
    return (
      <div className={styles.page}>
        <ProviderTopNav />
        <main className={styles.state}><section className={styles.card}>
          <Alert variant="error">{notice?.text ?? 'Provider portal access is unavailable.'}</Alert>
          <Link to="/provider/login">Return to provider sign in</Link>
        </section></main>
      </div>
    );
  }

  return (
    <div className={styles.page}>
      <ProviderTopNav />
      <main className={styles.shell}>
        <header className={styles.header}>
          <div>
            <p className={styles.eyebrow}>Provider portal</p>
            <h1 className="text-display">Manage your submitted profile</h1>
            <p className={styles.headerIntro}>Keep your public listing current and easy for members to understand.</p>
          </div>
        </header>
        {notice && <Alert variant={notice.variant} onDismiss={() => setNotice(null)}>{notice.text}</Alert>}
        {profile.profile_update?.review_status === 'PENDING_REVIEW' && (
          <Alert variant="warning">A profile update is awaiting review. You can keep revising this draft; members continue to see your last approved listing.</Alert>
        )}
        {profile.profile_update?.review_status === 'REJECTED' && (
          <Alert variant="error">Your last profile update was declined{profile.profile_update.rejection_reason ? `: ${profile.profile_update.rejection_reason}` : '.'} Revise the draft below and save it to resubmit.</Alert>
        )}
        {profile.profile_update?.review_status === 'APPROVED' && (
          <Alert variant="success">Your most recent profile update was approved{profile.profile_update.reviewed_at ? ` on ${new Date(profile.profile_update.reviewed_at).toLocaleDateString()}` : ''}.</Alert>
        )}
        <div className={styles.workspace} data-testid="provider-workspace">
          <div className={styles.feedbackDock}>
            <button
              ref={feedbackTriggerRef}
              type="button"
              className={styles.feedbackTrigger}
              aria-controls="provider-feedback-drawer"
              aria-expanded={feedbackOpen}
              onClick={() => setFeedbackOpen((open) => !open)}
            >
              <span aria-hidden="true">★</span>
              Member feedback
              <span className={styles.triggerChevron} aria-hidden="true">{feedbackOpen ? '⌃' : '⌄'}</span>
            </button>
            <aside
              id="provider-feedback-drawer"
              className={styles.feedbackDrawer}
              role="dialog"
              aria-labelledby="provider-feedback-heading"
              hidden={!feedbackOpen}
              data-testid="feedback-drawer"
            >
              <div className={styles.drawerHeader}>
                <div>
                  <p className={styles.drawerEyebrow}>Member feedback</p>
                  <h2 id="provider-feedback-heading">What members are saying</h2>
                </div>
                <button
                  ref={feedbackCloseRef}
                  type="button"
                  className={styles.drawerClose}
                  aria-label="Close member feedback"
                  onClick={() => setFeedbackOpen(false)}
                >
                  <span aria-hidden="true">×</span>
                  <span>Close</span>
                </button>
              </div>
              <p className={styles.rating}>
                {profile.average_rating?.toFixed(1) ?? '—'} ★ · {profile.review_count} review{profile.review_count === 1 ? '' : 's'}
              </p>
              <ReviewCardList
                reviews={profile.visible_reviews}
                formatTimestamp={formatTimestamp}
                emptyTitle="No member-visible review comments yet."
                emptyDescription="Visible member feedback will appear here after it has been submitted."
              />
            </aside>
          </div>
          <form className={styles.card + ' ' + styles.form} onSubmit={save}>
            <h2>Your profile</h2>
            <p className={styles.hint}>Welcome, {user?.full_name ?? 'provider'}. Unpublished listings save immediately. Changes to published listings are held for administrator review; publication and operational controls are never available here.</p>
            <Input label="Provider or practice name" id="portal-name" value={form.name ?? ''} onChange={(e) => update('name', e.target.value)} disabled={saving} required />
            <label className={styles.field}>Description
              <textarea className={styles.textarea} rows={5} value={form.description ?? ''} onChange={(e) => update('description', e.target.value || null)} disabled={saving} maxLength={5000} />
            </label>
            <div className={styles.choice}>
              <Input label="Public email" id="portal-email" type="email" value={form.email ?? ''} onChange={(e) => update('email', e.target.value || null)} disabled={saving} />
              <Input label="Public phone" id="portal-phone" value={form.phone ?? ''} onChange={(e) => update('phone', e.target.value || null)} disabled={saving} />
            </div>
            <Input label="Website" id="portal-website" value={form.website ?? ''} onChange={(e) => update('website', e.target.value || null)} disabled={saving} />
            <div className={styles.field}><span>Visit availability</span><div className={styles.choice}>
              <label><input type="radio" checked={form.visit_stability === 'STABLE_VISIT'} onChange={() => update('visit_stability', 'STABLE_VISIT')} disabled={saving} /> Stable visits</label>
              <label><input type="radio" checked={form.visit_stability === 'NOT_STABLE_VISIT'} onChange={() => update('visit_stability', 'NOT_STABLE_VISIT')} disabled={saving} /> Clinic-based</label>
            </div></div>
            <div className={styles.sectionDivider} />
            <div className={styles.field}><span>Specializations</span><div className={styles.specializations}>
              {specializations.map((item) => <label key={item.id}><input type="checkbox" checked={form.specialization_ids?.includes(item.id) ?? false} onChange={(e) => update('specialization_ids', e.target.checked ? [...(form.specialization_ids ?? []), item.id] : (form.specialization_ids ?? []).filter((id) => id !== item.id))} disabled={saving} /> {item.name}</label>)}
            </div></div>
            {profile.doctor_fields_available && <><div className={styles.sectionDivider} /><h2>Professional details</h2>
              <Input label="Professional title" id="portal-title" value={form.professional_title ?? ''} onChange={(e) => update('professional_title', e.target.value || null)} disabled={saving} />
              <label className={styles.field}>Biography<textarea className={styles.textarea} rows={4} value={form.biography ?? ''} onChange={(e) => update('biography', e.target.value || null)} disabled={saving} /></label>
              <Input label="Years of experience" id="portal-years" type="number" min="0" max="100" value={form.years_experience ?? ''} onChange={(e) => update('years_experience', e.target.value ? Number(e.target.value) : null)} disabled={saving} />
            </>}
            {([
              ['Locations', locations, setLocations, 'A JSON list of locations. Each entry needs address_line_1 and city.'],
              ['Phone contacts', phones, setPhones, 'A JSON list with country_code, number, and optional is_primary.'],
              ['Email contacts', emails, setEmails, 'A JSON list with email and optional is_primary.'],
              ['Photos', photos, setPhotos, 'A JSON list with storage_reference, optional alt_text/caption, display_order, and is_thumbnail.'],
              ...(profile.doctor_fields_available ? [['Qualifications', qualifications, setQualifications, 'A JSON list with title, institution, year_obtained, description, and display_order.']] as const : []),
            ] as const).map(([label, value, setter, hint]) => <label className={styles.field} key={label}>{label}
              <textarea className={styles.textarea} rows={5} value={value} onChange={(e) => setter(e.target.value)} disabled={saving} spellCheck={false} />
              <span className={styles.hint}>{hint}</span>
            </label>)}
            <div className={styles.choice}>
              <Button type="submit" loading={saving}>{profile.profile_update?.review_status === 'REJECTED' ? 'Revise and resubmit' : 'Save profile'}</Button>
              {profile.profile_update?.review_status !== 'APPROVED' && profile.profile_update && <Button type="button" variant="secondary" disabled={saving} onClick={() => void discardDraft()}>Discard draft and reload approved listing</Button>}
            </div>
          </form>
        </div>
      </main>
    </div>
  );
}
