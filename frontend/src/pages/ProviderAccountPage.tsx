import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '@/app/AuthContext';
import { extractErrorMessage, getApiErrorCode } from '@/api/client';
import * as providersApi from '@/api/providers';
import { useTimeSettings } from '@/app/TimeSettingsContext';
import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
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

  function populate(next: ProviderPortalProfile) {
    setProfile(next);
    setForm({
      name: next.name,
      description: next.description,
      email: next.email,
      phone: next.phone,
      website: next.website,
      visit_stability: next.visit_stability,
      specialization_ids: next.specializations.map((item) => item.id),
      professional_title: next.doctor_profile?.professional_title ?? null,
      biography: next.doctor_profile?.biography ?? null,
      years_experience: next.doctor_profile?.years_experience ?? null,
      experience_description: next.doctor_profile?.experience_description ?? null,
    });
    setLocations(formattedList(next.locations.map(({ id, provider_id, created_at, updated_at, ...item }) => item)));
    setPhones(formattedList(next.phones.map(({ id, provider_id, created_at, updated_at, ...item }) => item)));
    setEmails(formattedList(next.emails.map(({ id, provider_id, created_at, updated_at, ...item }) => item)));
    setPhotos(formattedList(next.photos.map(({ id, provider_id, created_at, updated_at, ...item }) => item)));
    setQualifications(formattedList(next.qualifications));
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
      setNotice({ variant: 'success', text: 'Your provider profile has been saved.' });
    } catch (err) {
      setNotice({ variant: 'error', text: err instanceof Error ? err.message : extractErrorMessage(err, 'Your profile could not be saved.') });
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <main className={styles.page}><div className={styles.loading} role="status"><LoadingSpinner /> Loading your provider portal…</div></main>;
  }
  if (!profile) {
    if (legacyApprovedAccount) {
      return (
        <main className={styles.page}>
          <section className={styles.card}>
            <p className={styles.eyebrow}>Provider account</p>
            <h1 className="text-display">Your provider account is approved.</h1>
            <p className={styles.empty}>
              Welcome, {user?.full_name ?? 'provider'}. Your directory listing is staged for the EquiConnected team.
            </p>
            <p className={styles.hint}>
              Profile editing is currently available through administrator review. We’ll let you know when more account tools are ready.
            </p>
            <Button type="button" variant="secondary" onClick={() => void logout()}>Sign out</Button>
          </section>
        </main>
      );
    }
    return <main className={styles.page}><section className={styles.card}><Alert variant="error">{notice?.text ?? 'Provider portal access is unavailable.'}</Alert><Link to="/provider/login">Return to provider sign in</Link></section></main>;
  }

  return (
    <main className={styles.page}>
      <div className={styles.shell}>
        <header className={styles.header}>
          <div>
            <p className={styles.eyebrow}>Provider portal</p>
            <h1 className="text-display">Manage your submitted profile</h1>
          </div>
          <Button type="button" variant="secondary" onClick={() => void logout()}>Sign out</Button>
        </header>
        {notice && <Alert variant={notice.variant} onDismiss={() => setNotice(null)}>{notice.text}</Alert>}
        <div className={styles.grid}>
          <form className={styles.card + ' ' + styles.form} onSubmit={save}>
            <h2>Your profile</h2>
            <p className={styles.hint}>Welcome, {user?.full_name ?? 'provider'}. Your changes are saved to your submitted profile. Publication and review decisions remain with the EquiConnected team.</p>
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
            <Button type="submit" loading={saving}>Save profile</Button>
          </form>
          <aside className={styles.card + ' ' + styles.reviews}>
            <h2>Member feedback</h2>
            <p className={styles.rating}>{profile.average_rating?.toFixed(1) ?? '—'} ★ · {profile.review_count} review{profile.review_count === 1 ? '' : 's'}</p>
            <ReviewCardList
              reviews={profile.visible_reviews}
              formatTimestamp={formatTimestamp}
              emptyTitle="No member-visible review comments yet."
              emptyDescription="Visible member feedback will appear here after it has been submitted."
            />
          </aside>
        </div>
      </div>
    </main>
  );
}