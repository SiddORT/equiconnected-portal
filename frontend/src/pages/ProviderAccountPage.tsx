import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '@/app/AuthContext';
import { extractErrorMessage } from '@/api/client';
import * as providersApi from '@/api/providers';
import { useTimeSettings } from '@/app/TimeSettingsContext';
import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { ProviderTopNav } from '@/components/layout/ProviderTopNav';
import { ReviewCardList } from '@/components/reviews/ReviewCard';
import {
  InvitationServiceFields,
  invitationServicePayload,
  invitationServiceValuesFromDraft,
  validateInvitationServices,
  type InvitationServiceValues,
} from '@/components/invite/InvitationProfileFields';
import {
  ProviderProfileCollections,
  type PortalLocation,
  type PortalPhoto,
  type PortalQualification,
} from '@/components/provider/ProviderProfileCollections';
import type { EmailEntry } from '@/components/admin/MultiEmailField';
import type { PhoneEntry } from '@/components/admin/MultiPhoneField';
import type {
  InvitationDraftProvider,
  ProviderPortalProfile,
  ProviderPortalUpdate,
  ProviderSpecializationBrief,
  VisitStability,
} from '@/types';
import { DEFAULT_COUNTRY } from '@/utils/countryCodes';
import { portalContactsFromProfile, portalScalarContactsFromCollections } from './providerPortalFormUtils';
import styles from './ProviderAccountPage.module.css';

type Notice = { variant: 'success' | 'error'; text: string } | null;
type PortalTab = 'basic' | 'professional' | 'services' | 'contact' | 'photos';

const PORTAL_TABS: Array<{ id: PortalTab; label: string }> = [
  { id: 'basic', label: 'Basic details' },
  { id: 'professional', label: 'Professional details' },
  { id: 'services', label: 'Services' },
  { id: 'contact', label: 'Contact & location' },
  { id: 'photos', label: 'Photos' },
];

function normalizePrimary<T extends { is_primary?: boolean }>(entries: T[]) {
  const primaryIndex = entries.findIndex((entry) => entry.is_primary);
  return entries.map((entry, index) => ({
    ...entry,
    is_primary: primaryIndex === -1 ? index === 0 : index === primaryIndex,
  }));
}

function normalizePhotos(entries: NonNullable<ProviderPortalUpdate['photos']>): PortalPhoto[] {
  const thumbnailIndex = entries.findIndex((entry) => entry.is_thumbnail);
  return entries.map((entry, index) => ({
    ...entry,
    display_order: entry.display_order ?? index,
    is_thumbnail: thumbnailIndex === -1 ? index === 0 : index === thumbnailIndex,
  }));
}

function normalizeQualifications(
  entries: NonNullable<ProviderPortalUpdate['qualifications']>
): PortalQualification[] {
  return entries.map((entry, index) => ({ ...entry, display_order: entry.display_order ?? index }));
}

export function ProviderAccountPage() {
  const { user } = useAuth();
  const { formatTimestamp } = useTimeSettings();
  const [profile, setProfile] = useState<ProviderPortalProfile | null>(null);
  const [specializations, setSpecializations] = useState<ProviderSpecializationBrief[]>([]);
  const [form, setForm] = useState<ProviderPortalUpdate>({});
  const [locations, setLocations] = useState<PortalLocation[]>([]);
  const [phones, setPhones] = useState<PhoneEntry[]>([]);
  const [emails, setEmails] = useState<EmailEntry[]>([]);
  const [photos, setPhotos] = useState<PortalPhoto[]>([]);
  const [qualifications, setQualifications] = useState<PortalQualification[]>([]);
  const [services, setServices] = useState<InvitationServiceValues>({
    visit_stability: 'NOT_STABLE_VISIT',
    maximum_working_radius_km: '',
    emergency_services_available: false,
    emergency_country_code: DEFAULT_COUNTRY.dialCode,
    emergency_iso_code: DEFAULT_COUNTRY.code,
    emergency_local_number: '',
  });
  const [serviceErrors, setServiceErrors] = useState<Record<string, string>>({});
  const [activeTab, setActiveTab] = useState<PortalTab>('basic');
  const [loading, setLoading] = useState(true);
  const [loadingSpecializations, setLoadingSpecializations] = useState(true);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState<Notice>(null);
  const [feedbackOpen, setFeedbackOpen] = useState(false);
  const feedbackTriggerRef = useRef<HTMLButtonElement>(null);
  const feedbackCloseRef = useRef<HTMLButtonElement>(null);
  const feedbackWasOpen = useRef(false);
  const serviceBaselineRef = useRef<InvitationServiceValues | null>(null);
  const formRef = useRef<HTMLFormElement>(null);
  const tabRefs = useRef<Partial<Record<PortalTab, HTMLButtonElement | null>>>({});
  const pendingInvalidFieldRef = useRef<HTMLElement | null>(null);

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
    setLocations(normalizePrimary(editable.locations));
    const contacts = portalContactsFromProfile(editable);
    setPhones(normalizePrimary(contacts.phones));
    setEmails(normalizePrimary(contacts.emails));
    setPhotos(normalizePhotos(editable.photos));
    setQualifications(normalizeQualifications(editable.qualifications));
    const serviceProfile = {
      name: editable.name,
      description: editable.description ?? null,
      email: editable.email ?? null,
      phone: editable.phone ?? null,
      website: editable.website ?? null,
      visit_stability: editable.visit_stability ?? next.visit_stability,
      maximum_working_radius_km: editable.maximum_working_radius_km !== undefined
        ? editable.maximum_working_radius_km
        : next.maximum_working_radius_km ?? null,
      emergency_services_available: editable.emergency_services_available !== undefined
        ? editable.emergency_services_available
        : next.emergency_services_available ?? false,
      emergency_contact_number: editable.emergency_contact_number !== undefined
        ? editable.emergency_contact_number
        : next.emergency_contact_number ?? null,
      status: 'ACTIVE',
      specialization_ids: editable.specialization_ids,
      locations: [],
      phones: [],
      emails: [],
      photos: [],
    } as InvitationDraftProvider;
    const nextServices = invitationServiceValuesFromDraft(serviceProfile);
    setServices(nextServices);
    serviceBaselineRef.current = nextServices;
    setServiceErrors({});
    setActiveTab('basic');
  }

  useEffect(() => {
    void (async () => {
      try {
        const [next, choices] = await Promise.all([
          providersApi.getProviderPortalProfile(),
          providersApi.getProviderPortalSpecializations(),
        ]);
        populate(next);
        setSpecializations([...new Map(
          choices.filter((choice) => choice.is_active).map((choice) => [choice.id, choice])
        ).values()]);
      } catch (err) {
        setNotice({ variant: 'error', text: extractErrorMessage(err, 'Your provider portal could not be loaded.') });
      } finally {
        setLoading(false);
        setLoadingSpecializations(false);
      }
    })();
  }, []);

  function update<K extends keyof ProviderPortalUpdate>(field: K, value: ProviderPortalUpdate[K]) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  function updateServices(next: InvitationServiceValues) {
    setServices(next);
    setServiceErrors({});
  }

  function changeTab(tab: PortalTab, focus = false) {
    setActiveTab(tab);
    if (focus) tabRefs.current[tab]?.focus();
  }

  function handleTabKeyDown(event: React.KeyboardEvent<HTMLButtonElement>) {
    const currentIndex = PORTAL_TABS.findIndex((tab) => tab.id === activeTab);
    let nextIndex: number | null = null;
    if (event.key === 'ArrowRight') nextIndex = (currentIndex + 1) % PORTAL_TABS.length;
    if (event.key === 'ArrowLeft') nextIndex = (currentIndex - 1 + PORTAL_TABS.length) % PORTAL_TABS.length;
    if (event.key === 'Home') nextIndex = 0;
    if (event.key === 'End') nextIndex = PORTAL_TABS.length - 1;
    if (nextIndex === null) return;
    event.preventDefault();
    changeTab(PORTAL_TABS[nextIndex].id, true);
  }

  function routeToInvalidField(field: HTMLElement) {
    const panel = field.closest<HTMLElement>('[data-tab-panel]');
    const tab = panel?.dataset.tabPanel as PortalTab | undefined;
    if (tab && tab !== activeTab) {
      pendingInvalidFieldRef.current = field;
      setActiveTab(tab);
      return;
    }
    field.focus();
    if ('reportValidity' in field && typeof field.reportValidity === 'function') field.reportValidity();
  }

  useEffect(() => {
    const field = pendingInvalidFieldRef.current;
    if (!field || !formRef.current?.contains(field)) return;
    pendingInvalidFieldRef.current = null;
    field.focus();
    if ('reportValidity' in field && typeof field.reportValidity === 'function') field.reportValidity();
  }, [activeTab]);

  async function save(event: React.FormEvent) {
    event.preventDefault();
    const baselineServices = serviceBaselineRef.current;
    const nextServiceErrors = validateInvitationServices(services);
    if (
      baselineServices?.visit_stability === 'STABLE_VISIT'
      && services.visit_stability === 'STABLE_VISIT'
      && !baselineServices.maximum_working_radius_km.trim()
      && !services.maximum_working_radius_km.trim()
    ) {
      delete nextServiceErrors.maximum_working_radius_km;
    }
    if (
      baselineServices?.emergency_services_available
      && services.emergency_services_available
      && !baselineServices.emergency_local_number.trim()
      && !services.emergency_local_number.trim()
      && baselineServices.emergency_country_code === services.emergency_country_code
      && baselineServices.emergency_iso_code === services.emergency_iso_code
    ) {
      delete nextServiceErrors.emergency_contact_number;
    }
    setServiceErrors({ ...nextServiceErrors });
    if (Object.keys(nextServiceErrors).length > 0) {
      const radiusLabel = nextServiceErrors.maximum_working_radius_km
        ? Array.from(formRef.current?.querySelectorAll('label') ?? [])
          .find((label) => label.textContent?.includes('Maximum working radius'))
        : undefined;
      const invalidServiceInput = radiusLabel?.control
        ?? formRef.current?.querySelector<HTMLInputElement>('[aria-label="Emergency contact number"]');
      if (invalidServiceInput instanceof HTMLElement) {
        routeToInvalidField(invalidServiceInput);
      } else {
        setActiveTab('services');
      }
      return;
    }
    const invalidFields = Array.from(formRef.current?.querySelectorAll<HTMLElement>(':invalid') ?? []);
    const grandfatheredMissingRadius = baselineServices?.visit_stability === 'STABLE_VISIT'
      && services.visit_stability === 'STABLE_VISIT'
      && !baselineServices.maximum_working_radius_km.trim()
      && !services.maximum_working_radius_km.trim();
    const invalidField = invalidFields.find((field) => {
      if (!grandfatheredMissingRadius || !(field instanceof HTMLInputElement) || field.type !== 'number') return true;
      const label = Array.from(formRef.current?.querySelectorAll<HTMLLabelElement>('label[for]') ?? [])
        .find((candidate) => candidate.htmlFor === field.id);
      return !label?.textContent?.includes('Maximum working radius');
    });
    if (invalidField) {
      routeToInvalidField(invalidField);
      return;
    }

    try {
      const scalarContacts = portalScalarContactsFromCollections(phones, emails);
      const servicePayload = invitationServicePayload(services);
      const body: ProviderPortalUpdate = {
        ...form,
        ...scalarContacts,
        visit_stability: services.visit_stability as VisitStability,
        maximum_working_radius_km: servicePayload.maximum_working_radius_km,
        emergency_services_available: services.emergency_services_available,
        emergency_contact_number: servicePayload.emergency_contact_number,
        locations,
        phones: phones.map(({ country_code, number, is_primary }) => ({
          country_code,
          number: number.trim(),
          is_primary,
        })),
        emails: emails.map(({ email, is_primary }) => ({ email: email.trim(), is_primary })),
        photos,
      };
      if (profile?.doctor_fields_available) {
        delete body.description;
        body.qualifications = qualifications;
      } else {
        delete body.professional_title;
        delete body.biography;
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

  async function uploadPhoto(
    { file, alt_text, caption }: { file: File; alt_text: string | null; caption: string | null }
  ): Promise<PortalPhoto> {
    const uploaded = await providersApi.uploadProviderPortalPhoto(file, { alt_text, caption });
    const portalPhoto = {
      ...uploaded,
      display_order: photos.length,
      is_thumbnail: photos.length === 0,
    };
    setPhotos((current) => {
      const nextPhoto = {
        ...uploaded,
        display_order: current.length,
        is_thumbnail: current.length === 0,
      };
      return [...current, nextPhoto];
    });
    setNotice({
      variant: 'success',
      text: 'Photo upload complete. Save your profile to include these photos in your listing or review request.',
    });
    return portalPhoto;
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

  const selectedSpecializationIds = form.specialization_ids ?? [];
  const selectedActiveSpecializationCount = specializations
    .filter((item) => selectedSpecializationIds.includes(item.id)).length;
  const allSpecializationsSelected = specializations.length > 0
    && selectedActiveSpecializationCount === specializations.length;
  const someSpecializationsSelected = selectedActiveSpecializationCount > 0 && !allSpecializationsSelected;

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
          <form ref={formRef} className={styles.card + ' ' + styles.form} onSubmit={save} noValidate>
            <h2>Your profile</h2>
            <p className={styles.hint}>Welcome, {user?.full_name ?? 'provider'}. Unpublished listings save immediately. Changes to published listings are held for administrator review; publication and operational controls are never available here.</p>
            <div
              role="tablist"
              aria-label="Provider profile sections"
              className={styles.tabs}
            >
              {PORTAL_TABS.map((tab) => (
                <button
                  key={tab.id}
                  ref={(node) => { tabRefs.current[tab.id] = node; }}
                  id={`provider-tab-${tab.id}`}
                  type="button"
                  role="tab"
                  aria-selected={activeTab === tab.id}
                  aria-controls={`provider-panel-${tab.id}`}
                  tabIndex={activeTab === tab.id ? 0 : -1}
                  className={styles.tab}
                  onClick={() => changeTab(tab.id)}
                  onKeyDown={handleTabKeyDown}
                  disabled={saving}
                >
                  {tab.label}
                </button>
              ))}
            </div>
            <div
              id="provider-panel-basic"
              role="tabpanel"
              aria-labelledby="provider-tab-basic"
              tabIndex={0}
              hidden={activeTab !== 'basic'}
              data-tab-panel="basic"
              className={styles.tabPanel}
            >
              <h3>Basic details</h3>
              <Input label="Provider or practice name" id="portal-name" value={form.name ?? ''} onChange={(e) => update('name', e.target.value)} disabled={saving} required />
              {!profile.doctor_fields_available && (
                <label className={styles.field}>Description
                  <textarea className={styles.textarea} rows={5} value={form.description ?? ''} onChange={(e) => update('description', e.target.value || null)} disabled={saving} maxLength={5000} />
                </label>
              )}
              <Input label="Website" id="portal-website" value={form.website ?? ''} onChange={(e) => update('website', e.target.value || null)} disabled={saving} />
            </div>
            <div
              id="provider-panel-services"
              role="tabpanel"
              aria-labelledby="provider-tab-services"
              tabIndex={0}
              hidden={activeTab !== 'services'}
              data-tab-panel="services"
              className={styles.tabPanel}
            >
              <section className={styles.specializationSection} aria-labelledby="portal-specializations-heading">
                <div className={styles.specializationHeader}>
                  <div>
                    <h3 id="portal-specializations-heading">Specializations</h3>
                    {loadingSpecializations
                      ? <p role="status">Loading specializations…</p>
                      : specializations.length === 0
                        ? <p>No active specializations are available.</p>
                        : <p>{selectedActiveSpecializationCount} of {specializations.length} selected</p>}
                  </div>
                  <div className={styles.specializationActions}>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      disabled={saving || loadingSpecializations || specializations.length === 0 || allSpecializationsSelected}
                      aria-pressed={allSpecializationsSelected ? 'true' : someSpecializationsSelected ? 'mixed' : 'false'}
                      onClick={() => update('specialization_ids', [...new Set(specializations.map((item) => item.id))])}
                    >
                      Select all
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      disabled={saving || loadingSpecializations || selectedSpecializationIds.length === 0}
                      aria-pressed="false"
                      onClick={() => update('specialization_ids', [])}
                    >
                      Clear all
                    </Button>
                  </div>
                </div>
                <div className={styles.specializations}>
                  {specializations.map((item) => (
                    <label key={item.id}>
                      <input
                        type="checkbox"
                        checked={selectedSpecializationIds.includes(item.id)}
                        onChange={(event) => update('specialization_ids', event.target.checked
                          ? [...new Set([...selectedSpecializationIds, item.id])]
                          : selectedSpecializationIds.filter((id) => id !== item.id))}
                        disabled={saving || loadingSpecializations}
                      />
                      {item.name}
                    </label>
                  ))}
                </div>
              </section>
              <div className={styles.sectionDivider} />
              <InvitationServiceFields value={services} onChange={updateServices} errors={serviceErrors} disabled={saving} />
            </div>
            <ProviderProfileCollections
              activeTab={activeTab}
              professionalContent={<>
                <h3>Professional details</h3>
                <Input label="Years of experience" id="portal-years" type="number" min="0" max="100" step="1" value={form.years_experience ?? ''} onChange={(e) => update('years_experience', e.target.value ? Number(e.target.value) : null)} disabled={saving} />
                {profile.doctor_fields_available && <>
                  <Input label="Professional title" id="portal-title" value={form.professional_title ?? ''} onChange={(e) => update('professional_title', e.target.value || null)} disabled={saving} />
                  <label className={styles.field}>Biography<textarea className={styles.textarea} rows={4} value={form.biography ?? ''} onChange={(e) => update('biography', e.target.value || null)} disabled={saving} /></label>
                  <label className={styles.field}>Experience notes
                    <textarea className={styles.textarea} rows={4} value={form.experience_description ?? ''} onChange={(e) => update('experience_description', e.target.value || null)} disabled={saving} maxLength={5000} />
                  </label>
                </>}
              </>}
              locations={locations}
              onLocationsChange={setLocations}
              phones={phones}
              onPhonesChange={setPhones}
              emails={emails}
              onEmailsChange={setEmails}
              photos={photos}
              onPhotosChange={setPhotos}
              onUploadPhoto={uploadPhoto}
              qualifications={qualifications}
              onQualificationsChange={setQualifications}
              showQualifications={profile.doctor_fields_available}
              disabled={saving}
            />
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
