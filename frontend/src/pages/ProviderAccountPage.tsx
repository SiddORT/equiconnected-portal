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
  DoctorVisit,
  DoctorVisitCreate,
  InvitationDraftProvider,
  ProviderPortalProfile,
  ProviderPortalUpdate,
  ProviderSpecializationBrief,
  VisitStability,
} from '@/types';
import { DEFAULT_COUNTRY } from '@/utils/countryCodes';
import { portalContactsFromProfile, portalScalarContactsFromCollections } from './providerPortalFormUtils';
import styles from './ProviderAccountPage.module.css';

type Notice = { variant: 'success' | 'warning' | 'error'; text: string } | null;
type PortalTab = 'basic' | 'professional' | 'services' | 'contact' | 'photos' | 'visits';

const BASE_PORTAL_TABS: Array<{ id: PortalTab; label: string }> = [
  { id: 'basic', label: 'Basic details' },
  { id: 'professional', label: 'Professional details' },
  { id: 'services', label: 'Services' },
  { id: 'contact', label: 'Contact & location' },
  { id: 'photos', label: 'Photos' },
];
const VISITS_TAB = { id: 'visits' as const, label: 'Visits' };

function portalTabs(canScheduleVisits: boolean) {
  return canScheduleVisits ? [...BASE_PORTAL_TABS, VISITS_TAB] : BASE_PORTAL_TABS;
}

function mayScheduleProviderVisits(
  profile: ProviderPortalProfile | null
): profile is ProviderPortalProfile {
  return Boolean(
    profile
    && profile.can_schedule_visits
    && profile.doctor_fields_available
    && profile.doctor_availability === 'VISITING'
  );
}

function localDateString(date = new Date()) {
  return [
    date.getFullYear(),
    String(date.getMonth() + 1).padStart(2, '0'),
    String(date.getDate()).padStart(2, '0'),
  ].join('-');
}

function formatCalendarDate(value: string) {
  const [year, month, day] = value.split('-').map(Number);
  return new Date(year, month - 1, day).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

function visitLocationDescription(location: DoctorVisitCreate['location']) {
  const coordinates = location.latitude != null || location.longitude != null
    ? `Coordinates: ${location.latitude ?? '—'}, ${location.longitude ?? '—'}`
    : null;
  return [
    location.name,
    location.address_line_1,
    location.address_line_2,
    [location.city, location.state_province, location.postal_code].filter(Boolean).join(', '),
    location.country,
    coordinates,
  ].filter(Boolean).join(', ');
}

function visitAdditionSnapshotKey(visit: DoctorVisitCreate) {
  return JSON.stringify({
    start_date: visit.start_date,
    end_date: visit.end_date,
    location: Object.fromEntries(
      Object.entries(visit.location).sort(([left], [right]) => (
        left < right ? -1 : left > right ? 1 : 0
      ))
    ),
  });
}

function isSavedVisitAddition(visit: DoctorVisitCreate, savedAdditions: DoctorVisitCreate[]) {
  const key = visitAdditionSnapshotKey(visit);
  return savedAdditions.some((saved) => visitAdditionSnapshotKey(saved) === key);
}

function isUnchangedPastVisit(
  visit: DoctorVisitCreate,
  savedAdditions: DoctorVisitCreate[],
  today: string
) {
  return visit.start_date < today && isSavedVisitAddition(visit, savedAdditions);
}

function validateVisitAdditions(
  additions: DoctorVisitCreate[],
  savedAdditions: DoctorVisitCreate[],
  recordedVisits: DoctorVisit[],
  today: string
): string | null {
  for (let index = 0; index < additions.length; index += 1) {
    const visit = additions[index];
    if (!visit.start_date || !visit.end_date) return 'Each proposed visit needs a start and end date.';
    if (visit.start_date < today && !isSavedVisitAddition(visit, savedAdditions)) {
      return 'New visits must start today or later.';
    }
    if (visit.start_date > visit.end_date) return 'A visit end date must be on or after its start date.';
    if (!visit.location.address_line_1.trim() || !visit.location.city.trim()) {
      return 'Each proposed visit needs an address line and city.';
    }
    const overlaps = (other: Pick<DoctorVisitCreate, 'start_date' | 'end_date'>) =>
      visit.start_date <= other.end_date && other.start_date <= visit.end_date;
    if (recordedVisits.some(overlaps) || additions.some((other, otherIndex) => (
      otherIndex !== index && overlaps(other)
    ))) {
      return 'Visit dates cannot overlap another recorded or proposed visit.';
    }
  }
  return null;
}

function groupVisits(visits: DoctorVisit[], today: string) {
  return {
    previous: visits.filter((visit) => visit.end_date < today),
    current: visits.filter((visit) => visit.start_date <= today && visit.end_date >= today),
    upcoming: visits.filter((visit) => visit.start_date > today),
  };
}

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
  const [visitAdditions, setVisitAdditions] = useState<DoctorVisitCreate[]>([]);
  const [visitError, setVisitError] = useState<string | null>(null);
  const [locations, setLocations] = useState<PortalLocation[]>([]);
  const [phones, setPhones] = useState<PhoneEntry[]>([]);
  const [emails, setEmails] = useState<EmailEntry[]>([]);
  const [photos, setPhotos] = useState<PortalPhoto[]>([]);
  const [uploadedPhotoReferences, setUploadedPhotoReferences] = useState<string[]>([]);
  const [photoUploading, setPhotoUploading] = useState(false);
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
  const photoUploadInProgressRef = useRef(false);
  const profileSavingRef = useRef(false);
  const tabRefs = useRef<Partial<Record<PortalTab, HTMLButtonElement | null>>>({});
  const pendingInvalidFieldRef = useRef<HTMLElement | null>(null);
  const visibleTabs = portalTabs(mayScheduleProviderVisits(profile));

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
    setVisitAdditions(editable.visit_additions ?? []);
    setVisitError(null);
    setLocations(normalizePrimary(editable.locations));
    const contacts = portalContactsFromProfile(editable);
    setPhones(normalizePrimary(contacts.phones));
    setEmails(normalizePrimary(contacts.emails));
    setPhotos(normalizePhotos(editable.photos));
    setUploadedPhotoReferences([]);
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
    const tabs = portalTabs(mayScheduleProviderVisits(profile));
    const currentIndex = tabs.findIndex((tab) => tab.id === activeTab);
    let nextIndex: number | null = null;
    if (event.key === 'ArrowRight') nextIndex = (currentIndex + 1) % tabs.length;
    if (event.key === 'ArrowLeft') nextIndex = (currentIndex - 1 + tabs.length) % tabs.length;
    if (event.key === 'Home') nextIndex = 0;
    if (event.key === 'End') nextIndex = tabs.length - 1;
    if (nextIndex === null) return;
    event.preventDefault();
    changeTab(tabs[nextIndex].id, true);
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
    if (photoUploadInProgressRef.current) {
      setNotice({
        variant: 'warning',
        text: 'Wait for photo uploads to finish before saving your profile. Then save again to include the uploaded photos.',
      });
      return;
    }
    const includesUploadedPhotos = uploadedPhotoReferences.length > 0;
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
    if (mayScheduleProviderVisits(profile)) {
      const invalidVisit = validateVisitAdditions(
        visitAdditions,
        profile.editable_profile.visit_additions ?? [],
        profile.doctor_visits ?? [],
        localDateString()
      );
      setVisitError(invalidVisit);
      if (invalidVisit) {
        setActiveTab('visits');
        const index = visitAdditions.findIndex((visit) => (
          !visit.start_date
          || (
            visit.start_date < localDateString()
            && !isSavedVisitAddition(visit, profile.editable_profile.visit_additions ?? [])
          )
          || !visit.end_date
          || visit.start_date > visit.end_date
          || !visit.location.address_line_1.trim()
          || !visit.location.city.trim()
        ));
        const visit = visitAdditions[index];
        const invalidVisitId = !visit?.start_date || (
          visit.start_date < localDateString()
          && !isSavedVisitAddition(visit, profile.editable_profile.visit_additions ?? [])
        )
          ? `portal-visit-${index}-start-date`
          : !visit.end_date || visit.start_date > visit.end_date
            ? `portal-visit-${index}-end-date`
            : !visit.location.address_line_1.trim()
              ? `portal-visit-${index}-address-line-1`
              : !visit.location.city.trim()
                ? `portal-visit-${index}-city`
                : null;
        const visitField = invalidVisitId
          ? formRef.current?.querySelector<HTMLElement>(`#${invalidVisitId}`)
          : null;
        if (visitField) routeToInvalidField(visitField);
        else setActiveTab('visits');
        return;
      }
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
      if (mayScheduleProviderVisits(profile)) body.visit_additions = visitAdditions;
      if (profile?.doctor_fields_available) {
        delete body.description;
        body.qualifications = qualifications;
      } else {
        delete body.professional_title;
        delete body.biography;
        delete body.experience_description;
      }
      profileSavingRef.current = true;
      setSaving(true);
      setNotice(null);
      const updated = await providersApi.updateProviderPortalProfile(body);
      populate(updated);
      setNotice({
        variant: 'success',
        text: updated.profile_update?.review_status === 'PENDING_REVIEW'
          ? includesUploadedPhotos
            ? 'Your uploaded photos and profile changes were saved to a review request. Members continue to see your last approved listing until an administrator approves it.'
            : 'Your proposed profile update is awaiting administrator review. Your live listing is unchanged until approval.'
          : includesUploadedPhotos
            ? 'Your uploaded photos and profile changes were saved to your unpublished provider profile.'
            : 'Your unpublished provider profile has been saved.',
      });
    } catch (err) {
      setNotice({ variant: 'error', text: err instanceof Error ? err.message : extractErrorMessage(err, 'Your profile could not be saved.') });
    } finally {
      profileSavingRef.current = false;
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
    if (profileSavingRef.current) {
      throw new Error('Wait for your profile save to finish before uploading photos.');
    }
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
    setUploadedPhotoReferences((current) => [...new Set([...current, uploaded.storage_reference])]);
    setNotice({
      variant: 'success',
      text: 'Photo upload complete. The photo is not part of your profile yet. Select Save profile to include it; unpublished profiles save immediately, while changes to published listings await administrator review.',
    });
    return portalPhoto;
  }

  function updatePhotos(next: PortalPhoto[]) {
    setPhotos(next);
    const remainingReferences = new Set(next.map((photo) => photo.storage_reference));
    setUploadedPhotoReferences((current) => current.filter((reference) => remainingReferences.has(reference)));
  }

  function updatePhotoUploadState(uploading: boolean) {
    photoUploadInProgressRef.current = uploading;
    setPhotoUploading(uploading);
  }

  function updateVisitAddition(index: number, patch: Partial<DoctorVisitCreate>) {
    setVisitAdditions((current) => current.map((visit, itemIndex) => (
      itemIndex === index ? { ...visit, ...patch } : visit
    )));
    setVisitError(null);
  }

  function updateVisitLocation(
    index: number,
    patch: Partial<DoctorVisitCreate['location']>
  ) {
    setVisitAdditions((current) => current.map((visit, itemIndex) => (
      itemIndex === index
        ? { ...visit, location: { ...visit.location, ...patch } }
        : visit
    )));
    setVisitError(null);
  }

  function addVisitAddition() {
    setVisitAdditions((current) => [...current, {
      start_date: '',
      end_date: '',
      location: {
        name: null,
        address_line_1: '',
        address_line_2: null,
        city: '',
        state_province: null,
        country: null,
        postal_code: null,
      },
    }]);
    setVisitError(null);
    changeTab('visits');
  }

  function removeVisitAddition(index: number) {
    setVisitAdditions((current) => current.filter((_, itemIndex) => itemIndex !== index));
    setVisitError(null);
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
  const today = localDateString();
  const visitsByPeriod = groupVisits(profile.doctor_visits ?? [], today);

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
          <Alert variant="warning">A profile update is awaiting review. You can keep revising this draft; members continue to see your last approved listing until an administrator approves it.</Alert>
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
              {visibleTabs.map((tab) => (
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
            {mayScheduleProviderVisits(profile) && (
              <div
                id="provider-panel-visits"
                role="tabpanel"
                aria-labelledby="provider-tab-visits"
                tabIndex={0}
                hidden={activeTab !== 'visits'}
                data-tab-panel="visits"
                className={styles.tabPanel}
              >
                <div className={styles.visitHeading}>
                  <h3>Visit history and scheduling</h3>
                  <p>Recorded visits are read-only. New trips are proposed separately and do not change your approved schedule until they are saved and, for published listings, approved.</p>
                </div>
                <section className={styles.visitSection} aria-labelledby="visit-history-heading">
                  <h4 id="visit-history-heading">Recorded visit history</h4>
                  {([
                    ['Previous', visitsByPeriod.previous],
                    ['Current', visitsByPeriod.current],
                    ['Upcoming', visitsByPeriod.upcoming],
                  ] as const).map(([label, visits]) => (
                    <section className={styles.visitPeriod} key={label} aria-labelledby={`visit-period-${label.toLowerCase()}`}>
                      <h5 id={`visit-period-${label.toLowerCase()}`}>{label}</h5>
                      {visits.length === 0
                        ? <p className={styles.visitEmpty}>No {label.toLowerCase()} visits recorded.</p>
                        : <div className={styles.visitCards}>
                          {visits.map((visit) => (
                            <article className={styles.visitCard} key={visit.id}>
                              <p className={styles.visitDates}>
                                <time dateTime={visit.start_date}>{formatCalendarDate(visit.start_date)}</time>
                                {' – '}
                                <time dateTime={visit.end_date}>{formatCalendarDate(visit.end_date)}</time>
                              </p>
                              <p className={styles.visitLocation}>{visitLocationDescription(visit.location)}</p>
                            </article>
                          ))}
                        </div>}
                    </section>
                  ))}
                </section>
                <div className={styles.sectionDivider} />
                <section className={styles.visitSection} aria-labelledby="proposed-visits-heading">
                  <div className={styles.visitSectionHeader}>
                    <div>
                      <h4 id="proposed-visits-heading">Proposed visits</h4>
                      <p>{profile.profile_update?.review_status === 'PENDING_REVIEW'
                        ? 'These additions are awaiting administrator review. You can revise or remove them before resubmitting.'
                        : profile.profile_update?.review_status === 'REJECTED'
                          ? 'These additions were declined with your profile update. Revise or remove them before saving again.'
                          : 'Add trips here, then select Save profile to submit them. Leaving this tab never saves or submits changes.'}</p>
                    </div>
                    <Button type="button" variant="outline" size="sm" disabled={saving} onClick={addVisitAddition}>
                      Add visit
                    </Button>
                  </div>
                  {visitError && <Alert variant="error">{visitError}</Alert>}
                  {visitAdditions.length === 0
                    ? <p className={styles.visitEmpty}>No proposed visits. Recorded visits remain unchanged.</p>
                    : <div className={styles.visitCards}>
                      {visitAdditions.map((visit, index) => (
                        <fieldset className={styles.proposedVisit} key={index}>
                          <legend>Proposed visit {index + 1}</legend>
                          <div className={styles.visitFieldActions}>
                            <p>Not part of your recorded visit history until the change is saved and approved when review is required.</p>
                            <button
                              type="button"
                              className={styles.removeVisit}
                              onClick={() => removeVisitAddition(index)}
                              disabled={saving}
                              aria-label={`Remove proposed visit ${index + 1}`}
                            >
                              Remove
                            </button>
                          </div>
                          <div className={styles.visitGrid}>
                            <Input
                              label={`Visit ${index + 1} start date`}
                              id={`portal-visit-${index}-start-date`}
                              type="date"
                              value={visit.start_date}
                              min={isUnchangedPastVisit(visit, profile.editable_profile.visit_additions ?? [], today)
                                ? undefined
                                : today}
                              required
                              disabled={saving}
                              onChange={(event) => updateVisitAddition(index, { start_date: event.target.value })}
                            />
                            <Input
                              label={`Visit ${index + 1} end date`}
                              id={`portal-visit-${index}-end-date`}
                              type="date"
                              value={visit.end_date}
                              min={isUnchangedPastVisit(visit, profile.editable_profile.visit_additions ?? [], today)
                                ? visit.start_date
                                : visit.start_date || today}
                              required
                              disabled={saving}
                              onChange={(event) => updateVisitAddition(index, { end_date: event.target.value })}
                            />
                          </div>
                          <h5>Visit location</h5>
                          <div className={styles.visitGrid}>
                            <Input label={`Visit ${index + 1} location name`} value={visit.location.name ?? ''} onChange={(event) => updateVisitLocation(index, { name: event.target.value || null })} disabled={saving} />
                            <Input id={`portal-visit-${index}-address-line-1`} label={`Visit ${index + 1} address line 1`} value={visit.location.address_line_1} onChange={(event) => updateVisitLocation(index, { address_line_1: event.target.value })} disabled={saving} required />
                            <Input label={`Visit ${index + 1} address line 2`} value={visit.location.address_line_2 ?? ''} onChange={(event) => updateVisitLocation(index, { address_line_2: event.target.value || null })} disabled={saving} />
                            <Input id={`portal-visit-${index}-city`} label={`Visit ${index + 1} city`} value={visit.location.city} onChange={(event) => updateVisitLocation(index, { city: event.target.value })} disabled={saving} required />
                            <Input label={`Visit ${index + 1} state, province, or emirate`} value={visit.location.state_province ?? ''} onChange={(event) => updateVisitLocation(index, { state_province: event.target.value || null })} disabled={saving} />
                            <Input label={`Visit ${index + 1} country`} value={visit.location.country ?? ''} onChange={(event) => updateVisitLocation(index, { country: event.target.value || null })} disabled={saving} />
                            <Input label={`Visit ${index + 1} postal code`} value={visit.location.postal_code ?? ''} onChange={(event) => updateVisitLocation(index, { postal_code: event.target.value || null })} disabled={saving} />
                            <Input label={`Visit ${index + 1} latitude`} type="number" min="-90" max="90" step="0.000001" value={visit.location.latitude ?? ''} onChange={(event) => updateVisitLocation(index, { latitude: event.target.value ? Number(event.target.value) : null })} disabled={saving} />
                            <Input label={`Visit ${index + 1} longitude`} type="number" min="-180" max="180" step="0.000001" value={visit.location.longitude ?? ''} onChange={(event) => updateVisitLocation(index, { longitude: event.target.value ? Number(event.target.value) : null })} disabled={saving} />
                          </div>
                        </fieldset>
                      ))}
                    </div>}
                </section>
              </div>
            )}
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
              onPhotosChange={updatePhotos}
              onUploadPhoto={uploadPhoto}
              onPhotoUploadStateChange={updatePhotoUploadState}
              unsavedUploadedPhotoCount={uploadedPhotoReferences.length}
              qualifications={qualifications}
              onQualificationsChange={setQualifications}
              showQualifications={profile.doctor_fields_available}
              disabled={saving || photoUploading}
            />
            <div className={styles.choice}>
              <Button type="submit" loading={saving} disabled={photoUploading}>{profile.profile_update?.review_status === 'REJECTED' ? 'Revise and resubmit' : 'Save profile'}</Button>
              {photoUploading && <span role="status">Wait for photo uploads to finish before saving profile changes.</span>}
              {profile.profile_update?.review_status !== 'APPROVED' && profile.profile_update && <Button type="button" variant="secondary" disabled={saving || photoUploading} onClick={() => void discardDraft()}>Discard draft and reload approved listing</Button>}
            </div>
          </form>
        </div>
      </main>
    </div>
  );
}
