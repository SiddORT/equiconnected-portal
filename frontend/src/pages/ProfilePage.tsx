import { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import * as profileApi from '@/api/profile';
import { extractErrorMessage } from '@/api/client';
import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { FormField } from '@/components/ui/FormField';
import { Input } from '@/components/ui/Input';
import { LoadingScreen } from '@/components/ui/LoadingScreen';
import { LocationPicker, type GeographicLocationValue } from '@/components/ui/LocationPicker';
import { PhoneInput } from '@/components/ui/PhoneInput';
import {
  calculateProfileCompletion,
  type ProfileCompletionSection,
  type ProfileSectionId,
} from '@/features/member/profileCompletion';
import type { Horse, HorsePayload, MemberProfile, PersonalProfileUpdate, StableProfileUpdate } from '@/types';
import styles from './ProfilePage.module.css';

type Notice = { kind: 'success' | 'error' | 'info'; text: string } | null;
type LocationSection = 'personal' | 'stable';

const emptyHorse: HorsePayload = { name: '', sex: 'OTHER' };
const profileSectionIds = new Set<ProfileSectionId>(['personal', 'stable', 'horses']);

function optional(value: string): string | null {
  return value.trim() || null;
}

function phoneParts(value: string) {
  const match = value.match(/^(\+\d{1,4})[\s-]*(.*)$/);
  return { dialCode: match?.[1] ?? '+1', number: match?.[2] ?? value };
}

function toPersonal(profile: MemberProfile): PersonalProfileUpdate {
  return {
    first_name: profile.first_name ?? '', last_name: profile.last_name ?? '',
    mobile_number: profile.mobile_number ?? '', address: profile.address,
    country: profile.country ?? '', state_province: profile.state_province,
    city: profile.city ?? '', postal_code: profile.postal_code,
  };
}

function toStable(profile: MemberProfile): StableProfileUpdate {
  const stable = profile.stable_profile;
  return {
    name: stable?.name ?? '', description: stable?.description, address: stable?.address,
    country: stable?.country ?? '', state_province: stable?.state_province, city: stable?.city ?? '',
    postal_code: stable?.postal_code, contact_name: stable?.contact_name,
    contact_phone: stable?.contact_phone, contact_email: stable?.contact_email,
  };
}

function SectionStatus({ section }: { section: ProfileCompletionSection }) {
  return (
    <div className={`${styles.sectionStatus} ${section.complete ? styles.complete : styles.incomplete}`} data-testid={`${section.id}-section-status`}>
      <span className={styles.statusIcon} aria-hidden="true">{section.complete ? '✓' : '○'}</span>
      <div>
        <strong>{section.complete ? 'Complete' : `${section.missing.length} item${section.missing.length === 1 ? '' : 's'} remaining`}</strong>
        {!section.complete && <p>Missing: {section.missing.join(' ')}</p>}
      </div>
    </div>
  );
}

function ProfileProgressSummary({
  completion,
  compact = false,
}: {
  completion: ReturnType<typeof calculateProfileCompletion>;
  compact?: boolean;
}) {
  return (
    <div className={`${styles.progressSummary} ${compact ? styles.progressSummaryCompact : ''}`} data-testid="profile-progress-summary">
      <div className={styles.progressHeading}>
        <div>
          <p className={styles.eyebrow}>Profile readiness</p>
          <h2>{completion.isComplete ? 'Your profile is ready' : `${completion.percentage}% complete`}</h2>
        </div>
        <span className={styles.progressPercent} aria-label={`${completion.percentage}% complete`}>{completion.percentage}%</span>
      </div>
      <div
        className={styles.progressTrack}
        role="progressbar"
        aria-label="Profile completion"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={completion.percentage}
      >
        <span className={styles.progressValue} style={{ width: `${completion.percentage}%` }} />
      </div>
      <p className={styles.progressMessage}>
        {completion.isComplete
          ? 'Your core account, contact, and role details are ready for provider discovery.'
          : `${completion.totalItems - completion.completedItems} core item${completion.totalItems - completion.completedItems === 1 ? '' : 's'} remain${completion.totalItems - completion.completedItems === 1 ? 's' : ''}. ${completion.nextAction}`}
      </p>
    </div>
  );
}

function HorseForm({
  initial, onCancel, onSave, saving,
}: { initial: HorsePayload; onCancel: () => void; onSave: (horse: HorsePayload) => Promise<void>; saving: boolean }) {
  const [form, setForm] = useState<HorsePayload>(initial);
  const [error, setError] = useState<string | null>(null);
  const change = (field: keyof HorsePayload, value: string) => setForm((current) => ({ ...current, [field]: value }));
  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!form.name.trim()) return setError('Horse name is required.');
    if (!form.sex) return setError('Horse sex is required.');
    setError(null);
    await onSave({
      ...form, name: form.name.trim(), registered_name: optional(form.registered_name ?? ''),
      breed: optional(form.breed ?? ''), date_of_birth: optional(form.date_of_birth ?? ''),
      color: optional(form.color ?? ''), primary_discipline: optional(form.primary_discipline ?? ''),
      registration_number: optional(form.registration_number ?? ''), microchip_number: optional(form.microchip_number ?? ''),
      description: optional(form.description ?? ''),
    });
  };
  return (
    <form className={styles.horseForm} onSubmit={submit} noValidate>
      {error && <Alert variant="error" onDismiss={() => setError(null)}>{error}</Alert>}
      <h3 className={styles.formGroupHeading}>Required basics</h3>
      <p className={styles.formHelp}>A name and sex are the only horse details needed for profile completion.</p>
      <div className={styles.grid}>
        <Input label="Horse name" value={form.name} onChange={(e) => change('name', e.target.value)} required />
        <FormField label="Sex" required htmlFor="horse-sex">
          <select id="horse-sex" className={styles.select} value={form.sex} onChange={(e) => change('sex', e.target.value)}>
            <option value="MARE">Mare</option><option value="GELDING">Gelding</option>
            <option value="STALLION">Stallion</option><option value="FILLY">Filly</option>
            <option value="COLT">Colt</option><option value="OTHER">Other</option>
          </select>
        </FormField>
      </div>
      <h3 className={styles.formGroupHeading}>Optional details</h3>
      <p className={styles.formHelp}>Add extended information when it is useful. These fields do not affect profile completion.</p>
      <div className={styles.grid}>
        <Input label="Registered name" value={form.registered_name ?? ''} onChange={(e) => change('registered_name', e.target.value)} />
        <Input label="Breed" value={form.breed ?? ''} onChange={(e) => change('breed', e.target.value)} />
        <Input label="Date of birth" type="date" value={form.date_of_birth ?? ''} onChange={(e) => change('date_of_birth', e.target.value)} />
        <Input label="Color" value={form.color ?? ''} onChange={(e) => change('color', e.target.value)} />
        <Input label="Primary discipline" value={form.primary_discipline ?? ''} onChange={(e) => change('primary_discipline', e.target.value)} />
        <Input label="Registration number" value={form.registration_number ?? ''} onChange={(e) => change('registration_number', e.target.value)} />
        <Input label="Microchip number" value={form.microchip_number ?? ''} onChange={(e) => change('microchip_number', e.target.value)} />
      </div>
      <FormField label="Description" optional htmlFor="horse-description">
        <textarea id="horse-description" className={styles.textarea} value={form.description ?? ''} onChange={(e) => change('description', e.target.value)} rows={3} />
      </FormField>
      <div className={styles.actions}><Button type="button" variant="ghost" onClick={onCancel}>Cancel</Button><Button type="submit" loading={saving}>Save horse</Button></div>
    </form>
  );
}

export function ProfilePage() {
  const [searchParams] = useSearchParams();
  const [profile, setProfile] = useState<MemberProfile | null>(null);
  const [personal, setPersonal] = useState<PersonalProfileUpdate | null>(null);
  const [stable, setStable] = useState<StableProfileUpdate | null>(null);
  const [editingHorse, setEditingHorse] = useState<Horse | null | 'new'>(null);
  const [notice, setNotice] = useState<Notice>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<'personal' | 'stable' | 'horse' | null>(null);
  const [lookupMessage, setLookupMessage] = useState<Record<LocationSection, string>>({ personal: '', stable: '' });

  useEffect(() => {
    profileApi.getProfile().then((data) => {
      setProfile(data); setPersonal(toPersonal(data)); setStable(toStable(data));
    }).catch((error) => setNotice({ kind: 'error', text: extractErrorMessage(error, 'We could not load your profile.') }))
      .finally(() => setLoading(false));
  }, []);

  const roles = useMemo(() => new Set(profile?.roles ?? []), [profile]);
  const canManageStable = roles.has('stable_manager');
  const canManageHorses = roles.has('horse_owner');
  const requestedSection = searchParams.get('section');

  useEffect(() => {
    if (!profile || !requestedSection || !profileSectionIds.has(requestedSection as ProfileSectionId)) return;
    const target = document.getElementById(`${requestedSection}-profile-section`);
    const heading = target?.querySelector<HTMLElement>('[data-profile-section-heading]');
    if (!target || !heading) return;
    const animationFrame = window.requestAnimationFrame(() => {
      target.scrollIntoView?.({ behavior: 'smooth', block: 'start' });
      heading.focus({ preventScroll: true });
    });
    return () => window.cancelAnimationFrame(animationFrame);
  }, [profile, requestedSection]);

  const setLocation = (section: LocationSection, location: GeographicLocationValue) => {
    if (section === 'personal') setPersonal((current) => current && ({ ...current, ...location }));
    else setStable((current) => current && ({ ...current, ...location }));
  };
  const triggerLookup = async (section: LocationSection) => {
    const data = section === 'personal' ? personal : stable;
    if (!data?.country || !data.postal_code?.trim()) return;
    setLookupMessage((current) => ({ ...current, [section]: 'Looking up location…' }));
    try {
      const result = await profileApi.lookupPostalCode(data.country, data.postal_code);
      if (result.status === 'match') {
        setLocation(section, { country: data.country, state_province: result.state_province ?? data.state_province ?? '', city: result.city ?? data.city ?? '' });
        setLookupMessage((current) => ({ ...current, [section]: 'Location details filled where available. You can edit them.' }));
      } else {
        setLookupMessage((current) => ({ ...current, [section]: result.status === 'no_match' ? 'No match found. Please enter the location details.' : 'Lookup is unavailable. Please enter the location details.' }));
      }
    } catch {
      setLookupMessage((current) => ({ ...current, [section]: 'Lookup is unavailable. Please enter the location details.' }));
    }
  };
  const savePersonal = async () => {
    if (!personal) return;
    if (!personal.first_name.trim() || !personal.last_name.trim() || !personal.mobile_number.trim() || !personal.country || !personal.city.trim()) {
      return setNotice({ kind: 'error', text: 'Complete all required personal fields before saving.' });
    }
    setSaving('personal');
    try {
      const saved = await profileApi.savePersonal({ ...personal, address: optional(personal.address ?? ''), state_province: optional(personal.state_province ?? ''), postal_code: optional(personal.postal_code ?? '') });
      setProfile(saved); setPersonal(toPersonal(saved)); setNotice({ kind: 'success', text: 'Personal information saved.' });
    } catch (error) { setNotice({ kind: 'error', text: extractErrorMessage(error, 'Personal information could not be saved.') }); }
    finally { setSaving(null); }
  };
  const saveStable = async () => {
    if (!stable) return;
    if (!stable.name.trim()) return setNotice({ kind: 'error', text: 'Stable name is required before saving.' });
    setSaving('stable');
    try {
      const saved = await profileApi.saveStable({ ...stable, name: stable.name.trim() });
      setProfile((current) => current && ({ ...current, stable_profile: saved })); setStable(toStable({ ...profile!, stable_profile: saved })); setNotice({ kind: 'success', text: 'Stable profile saved.' });
    } catch (error) { setNotice({ kind: 'error', text: extractErrorMessage(error, 'Stable profile could not be saved.') }); }
    finally { setSaving(null); }
  };
  const saveHorse = async (payload: HorsePayload) => {
    setSaving('horse');
    try {
      const horse = editingHorse === 'new' ? await profileApi.createHorse(payload) : await profileApi.saveHorse(editingHorse!.id, payload);
      setProfile((current) => current && ({ ...current, horses: editingHorse === 'new' ? [...current.horses, horse] : current.horses.map((item) => item.id === horse.id ? horse : item) }));
      setEditingHorse(null); setNotice({ kind: 'success', text: 'Horse saved.' });
    } catch (error) { setNotice({ kind: 'error', text: extractErrorMessage(error, 'Horse could not be saved.') }); }
    finally { setSaving(null); }
  };
  const removeHorse = async (horse: Horse) => {
    if (!window.confirm(`Remove ${horse.name}? This cannot be undone.`)) return;
    try { await profileApi.deleteHorse(horse.id); setProfile((current) => current && ({ ...current, horses: current.horses.filter((item) => item.id !== horse.id) })); setNotice({ kind: 'success', text: 'Horse removed.' }); }
    catch (error) { setNotice({ kind: 'error', text: extractErrorMessage(error, 'Horse could not be removed.') }); }
  };
  const uploadPhoto = async (horse: Horse, file: File) => {
    if (!['image/jpeg', 'image/png', 'image/gif', 'image/webp'].includes(file.type) || file.size > 10 * 1024 * 1024) return setNotice({ kind: 'error', text: 'Choose a JPEG, PNG, GIF, or WebP image no larger than 10 MB.' });
    try { const saved = await profileApi.uploadHorsePhoto(horse.id, file); setProfile((current) => current && ({ ...current, horses: current.horses.map((item) => item.id === saved.id ? saved : item) })); setNotice({ kind: 'success', text: 'Horse photo uploaded.' }); }
    catch (error) { setNotice({ kind: 'error', text: extractErrorMessage(error, 'Horse photo could not be uploaded.') }); }
  };

  if (loading) return <LoadingScreen message="Loading your profile…" />;
  if (!profile || !personal || !stable) return <main className={styles.page}><Alert variant="error">We could not load your profile. <button className={styles.linkButton} onClick={() => window.location.reload()}>Try again</button></Alert></main>;
  const completion = calculateProfileCompletion(profile);
  const personalStatus = completion.sections.find((section) => section.id === 'personal')!;
  const stableStatus = completion.sections.find((section) => section.id === 'stable');
  const horsesStatus = completion.sections.find((section) => section.id === 'horses');
  const personalPhone = phoneParts(personal.mobile_number);
  const stablePhone = phoneParts(stable.contact_phone ?? '');
  const editingHorseId = editingHorse && typeof editingHorse === 'object' ? editingHorse.id : null;
  return (
    <main className={styles.page}>
      <header className={styles.header}><div><p className={styles.eyebrow}>Verified member area</p><h1 className="text-display">Your profile</h1><p>Keep your contact, stable, and horse information up to date.</p></div><Link to="/providers" className={styles.homeLink}>Browse providers</Link></header>
      {notice && <Alert variant={notice.kind === 'info' ? 'info' : notice.kind} onDismiss={() => setNotice(null)}>{notice.text}</Alert>}
      <ProfileProgressSummary completion={completion} />
      <section id="personal-profile-section" aria-labelledby="personal-profile-heading" className={styles.sectionAnchor}>
      <Card className={styles.section}><div className={styles.sectionHeader}><div><h2 id="personal-profile-heading" data-profile-section-heading tabIndex={-1}>Account, contact, and location</h2><p>Core fields marked with an asterisk help providers and your care team reach you.</p></div><SectionStatus section={personalStatus} /></div>
        <div className={styles.accountStatus}><strong>Email account status</strong><span><span aria-hidden="true">✓</span> Verified: {profile.email}</span></div>
        <div className={styles.formGroup}>
          <h3 className={styles.formGroupHeading}>Account and contact</h3>
          <p className={styles.formHelp}>Your email is verified and cannot be changed here. Keep your name and mobile number current.</p>
        <div className={styles.grid}>
          <Input label="First name" required value={personal.first_name} onChange={(e) => setPersonal({ ...personal, first_name: e.target.value })} />
          <Input label="Last name" required value={personal.last_name} onChange={(e) => setPersonal({ ...personal, last_name: e.target.value })} />
          <FormField label="Mobile number" required><PhoneInput countryCode={personalPhone.dialCode} number={personalPhone.number} onCountryCodeChange={(code) => setPersonal({ ...personal, mobile_number: `${code} ${personalPhone.number}` })} onNumberChange={(number) => setPersonal({ ...personal, mobile_number: `${personalPhone.dialCode} ${number}` })} /></FormField>
        </div>
        </div>
        <div className={styles.formGroup}>
          <h3 className={styles.formGroupHeading}>Personal location</h3>
          <p className={styles.formHelp}>Use your current address. State or province is only required where the selected country uses one.</p>
          <Input label="Address" required value={personal.address ?? ''} onChange={(e) => setPersonal({ ...personal, address: e.target.value })} />
        <LocationPicker value={{ country: personal.country, state_province: personal.state_province ?? '', city: personal.city }} onChange={(value) => setLocation('personal', value)} required idPrefix="personal-location" />
        <Input label="Postal / ZIP code" required value={personal.postal_code ?? ''} onChange={(e) => setPersonal({ ...personal, postal_code: e.target.value })} onBlur={() => triggerLookup('personal')} hint={lookupMessage.personal || 'Enter a postal/ZIP code to look up available location details.'} />
        </div>
        <div className={styles.actions}><Button onClick={savePersonal} loading={saving === 'personal'}>Save personal information</Button></div>
      </Card></section>
      {canManageStable && stableStatus && <section id="stable-profile-section" aria-labelledby="stable-profile-heading" className={styles.sectionAnchor}><Card className={styles.section}><div className={styles.sectionHeader}><div><h2 id="stable-profile-heading" data-profile-section-heading tabIndex={-1}>Stable Manager</h2><p>Save stable details independently. A stable photo is not part of this profile.</p></div><SectionStatus section={stableStatus} /></div>
        <div className={styles.formGroup}>
          <h3 className={styles.formGroupHeading}>Stable identity</h3>
          <p className={styles.formHelp}>Your stable name and location make it easier to coordinate care.</p>
          <div className={styles.grid}><Input label="Stable name" required value={stable.name} onChange={(e) => setStable({ ...stable, name: e.target.value })} /><Input label="Stable address" required value={stable.address ?? ''} onChange={(e) => setStable({ ...stable, address: e.target.value })} /></div>
        </div>
        <FormField label="Stable description" optional htmlFor="stable-description"><textarea id="stable-description" className={styles.textarea} rows={3} value={stable.description ?? ''} onChange={(e) => setStable({ ...stable, description: e.target.value })} /></FormField>
        <div className={styles.formGroup}>
          <h3 className={styles.formGroupHeading}>Stable location</h3>
          <LocationPicker value={{ country: stable.country ?? '', state_province: stable.state_province ?? '', city: stable.city ?? '' }} onChange={(value) => setLocation('stable', value)} required idPrefix="stable-location" />
          <Input label="Postal / ZIP code" required value={stable.postal_code ?? ''} onChange={(e) => setStable({ ...stable, postal_code: e.target.value })} onBlur={() => triggerLookup('stable')} hint={lookupMessage.stable || 'Enter a postal/ZIP code to look up available location details.'} />
        </div>
        <div className={styles.formGroup}>
          <h3 className={styles.formGroupHeading}>Stable contact</h3>
          <p className={styles.formHelp}>Use a contact who can help providers reach the stable.</p>
          <div className={styles.grid}><Input label="Contact name" required value={stable.contact_name ?? ''} onChange={(e) => setStable({ ...stable, contact_name: e.target.value })} /><Input label="Contact email" required type="email" value={stable.contact_email ?? ''} onChange={(e) => setStable({ ...stable, contact_email: e.target.value })} /><FormField label="Contact phone" required><PhoneInput countryCode={stablePhone.dialCode} number={stablePhone.number} onCountryCodeChange={(code) => setStable({ ...stable, contact_phone: `${code} ${stablePhone.number}` })} onNumberChange={(number) => setStable({ ...stable, contact_phone: `${stablePhone.dialCode} ${number}` })} /></FormField></div>
        </div>
        <div className={styles.actions}><Button onClick={saveStable} loading={saving === 'stable'}>Save stable profile</Button></div>
      </Card></section>}
      {canManageHorses && horsesStatus && <section id="horses-profile-section" aria-labelledby="horses-profile-heading" className={styles.sectionAnchor}><Card className={styles.section}><div className={styles.sectionHeader}><div><h2 id="horses-profile-heading" data-profile-section-heading tabIndex={-1}>Horse Owner</h2><p>Add at least one horse with its required basics, then manage every horse individually.</p></div><div className={styles.sectionActions}><SectionStatus section={horsesStatus} /><Button onClick={() => setEditingHorse('new')} disabled={editingHorse !== null}>Add horse</Button></div></div>
        {editingHorse === 'new' && <HorseForm initial={emptyHorse} onCancel={() => setEditingHorse(null)} onSave={saveHorse} saving={saving === 'horse'} />}
        <div className={styles.horseList}>{profile.horses.length === 0 && editingHorse !== 'new' ? <p className={styles.empty}>No horses added yet.</p> : profile.horses.map((horse) => editingHorseId === horse.id ? <HorseForm key={horse.id} initial={horse} onCancel={() => setEditingHorse(null)} onSave={saveHorse} saving={saving === 'horse'} /> : <article key={horse.id} className={styles.horseCard}><div className={styles.horseIdentity}>{horse.photo_reference ? <img src={horse.photo_reference} alt={`${horse.name}`} /> : <div className={styles.photoPlaceholder}>Horse photo</div>}<div><h3>{horse.name}</h3><p>{horse.sex.toLowerCase()} {horse.breed ? `• ${horse.breed}` : ''}</p></div></div><div className={styles.horseButtons}><label className={styles.photoButton}>Upload photo<input type="file" accept="image/jpeg,image/png,image/gif,image/webp" onChange={(e) => e.target.files?.[0] && uploadPhoto(horse, e.target.files[0])} /></label>{horse.photo_reference && <Button variant="ghost" size="sm" onClick={async () => { try { await profileApi.removeHorsePhoto(horse.id); setProfile((current) => current && ({ ...current, horses: current.horses.map((item) => item.id === horse.id ? { ...item, photo_reference: null } : item) })); setNotice({ kind: 'success', text: 'Horse photo removed.' }); } catch (error) { setNotice({ kind: 'error', text: extractErrorMessage(error, 'Horse photo could not be removed.') }); } }}>Remove photo</Button>}<Button variant="outline" size="sm" onClick={() => setEditingHorse(horse)}>Edit</Button><Button variant="danger" size="sm" onClick={() => removeHorse(horse)}>Remove</Button></div></article>)}</div>
      </Card></section>}
    </main>
  );
}