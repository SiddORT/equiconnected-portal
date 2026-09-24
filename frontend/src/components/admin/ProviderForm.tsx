/**
 * ProviderForm — shared create / edit form for providers.
 *
 * Props:
 *   initialData — pre-populate fields when editing (undefined = create mode)
 *   onSuccess(provider) — called with the saved provider on success
 *   onCancel() — called when the user dismisses the form
 */
import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { Country } from 'country-state-city';
import { extractErrorMessage } from '@/api/client';
import { lookupProviderPostalCode, type PostalCandidate } from '@/api/auth';
import {
  addProviderEmail,
  addProviderPhone,
  addProviderSpecialization,
  createProvider,
  createProviderLocation,
  getProvider,
  removeProviderEmail,
  removeProviderPhone,
  removeProviderSpecialization,
  updateProvider,
  updateProviderLocation,
  updateProviderPublication,
  updateProviderStatus,
  uploadProviderPhoto,
} from '@/api/providers';
import { listSpecializations } from '@/api/specializations';
import { listLanguages } from '@/api/languages';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { FormField } from '@/components/ui/FormField';
import { Input } from '@/components/ui/Input';
import { LocationPicker } from '@/components/ui/LocationPicker';
import { Select } from '@/components/ui/Select';
import { MultiEmailField, type EmailEntry } from './MultiEmailField';
import { MultiPhoneField, type PhoneEntry } from './MultiPhoneField';
import { ProviderWizardHeader, ProviderWizardReview } from './ProviderWizard';
import { SignupMultiSelect } from '@/pages/SignupMultiSelect';
import type {
  InvitationDraftPayload,
  InvitationDraftProvider,
  InvitationSpecialization,
  Provider,
  ProviderCreate,
  ProviderLocationCreate,
  ProviderStatus,
  ProviderType,
  PublicationStatus,
  Specialization,
  VisitStability,
  Language,
  QualificationCreate,
} from '@/types';
import styles from './ProviderForm.module.css';
import wizardStyles from './ProviderWizard.module.css';

const PROVIDER_TYPE_OPTIONS = [
  { value: 'HOSPITAL', label: 'Hospital' },
  { value: 'CLINIC', label: 'Clinic' },
  { value: 'DOCTOR', label: 'Doctor / Vet' },
];
const VISIT_STABILITY_OPTIONS = [
  { value: 'STABLE_VISIT', label: 'Yes' },
  { value: 'NOT_STABLE_VISIT', label: 'No' },
];
const INVITATION_VISIT_STABILITY_OPTIONS = [
  { value: 'STABLE_VISIT', label: 'Yes' },
  { value: 'NOT_STABLE_VISIT', label: 'No' },
];
const STATUS_OPTIONS = [
  { value: 'ACTIVE', label: 'Active' },
  { value: 'INACTIVE', label: 'Inactive' },
];
const PUBLICATION_OPTIONS = [
  { value: 'UNPUBLISHED', label: 'Unpublished' },
  { value: 'PUBLISHED', label: 'Published' },
];

const WIZARD_STEPS = [
  { title: 'Basic details', description: 'Add the provider identity, specializations, languages, and photo.' },
  { title: 'Professional details', description: 'Add professional background and qualifications.' },
  { title: 'Services', description: 'Choose visit options, emergency care, and visibility.' },
  { title: 'Contact & location', description: 'Enter a primary email and one provider location.' },
  { title: 'Review & create', description: 'Check everything before creating the provider.' },
];

function wizardStepForField(key: string): number {
  if (key === 'provider_type' || key === 'name') return 0;
  if (['first_name', 'last_name', 'years_experience'].includes(key) || key.startsWith('qualification_')) return 1;
  if (['visit_stability', 'maximum_working_radius_km', 'emergency_contact_number'].includes(key)) return 2;
  return 3;
}

interface LocationValues {
  name: string;
  address_line_1: string;
  address_line_2: string;
  city: string;
  state_province: string;
  country: string;
  postal_code: string;
  latitude: string;
  longitude: string;
}

const EMPTY_LOCATION: LocationValues = {
  name: '',
  address_line_1: '',
  address_line_2: '',
  city: '',
  state_province: '',
  country: '',
  postal_code: '',
  latitude: '',
  longitude: '',
};

/**
 * Invitation mode — the form is driven by a public invitation token instead
 * of the admin API. Status/publication controls are hidden, the provider
 * type is fixed, and save/submit are delegated to the adapter callbacks.
 */
export interface InvitationFormConfig {
  providerType: ProviderType;
  initial: InvitationDraftProvider;
  loadSpecializations: () => Promise<InvitationSpecialization[]>;
  onSaveDraft: (payload: InvitationDraftPayload) => Promise<void>;
  onSubmit: (payload: InvitationDraftPayload) => Promise<void>;
  externalErrors?: Record<string, string>;
}

interface ProviderFormProps {
  initialData?: Provider;
  invitation?: InvitationFormConfig;
  onSuccess?: (provider: Provider) => void;
  onCancel?: () => void;
}

export function ProviderForm({ initialData, invitation, onSuccess, onCancel }: ProviderFormProps) {
  const isEdit = Boolean(initialData);
  const inv = invitation;
  const wizard = !inv;
  const [wizardStep, setWizardStep] = useState(0);
  const [reviewReady, setReviewReady] = useState(false);
  const submissionInProgress = useRef(false);
  const submissionCompleted = useRef(false);
  const visitStabilityOptions = inv
    ? INVITATION_VISIT_STABILITY_OPTIONS
    : VISIT_STABILITY_OPTIONS;

  const [providerType, setProviderType] = useState<string>(
    inv?.providerType ?? initialData?.provider_type ?? ''
  );
  const stepOrder = providerType === 'DOCTOR' ? [0, 1, 2, 3, 4] : [0, 2, 3, 4];
  const wizardPosition = stepOrder.indexOf(wizardStep);
  const [name, setName] = useState(inv?.initial.name ?? initialData?.name ?? '');
  const [description, setDescription] = useState(
    inv?.initial.description ?? initialData?.description ?? ''
  );
  const [website, setWebsite] = useState(inv?.initial.website ?? initialData?.website ?? '');
  const [phoneEntries, setPhoneEntries] = useState<PhoneEntry[]>(() => {
    if (inv) {
      return inv.initial.phones.map((p) => ({
        country_code: p.country_code,
        number: p.number,
        is_primary: p.is_primary ?? false,
      }));
    }
    if (!initialData) return [];
    if (initialData.phones.length > 0) {
      return initialData.phones.map((p) => ({
        id: p.id,
        country_code: p.country_code,
        number: p.number,
        is_primary: p.is_primary,
      }));
    }
    // Legacy fallback: providers saved before the multi-phone migration.
    if (initialData.phone) {
      const m = initialData.phone.trim().match(/^(\+\d{1,4})[\s.-]+(.+)$/);
      return [
        m
          ? { country_code: m[1], number: m[2], is_primary: true }
          : { country_code: '+1', number: initialData.phone.trim(), is_primary: true },
      ];
    }
    return [];
  });
  const [emailEntries, setEmailEntries] = useState<EmailEntry[]>(() => {
    if (inv) {
      return inv.initial.emails.map((e) => ({
        email: e.email,
        is_primary: e.is_primary ?? false,
      }));
    }
    if (!initialData) return [];
    if (initialData.emails.length > 0) {
      return initialData.emails.map((e) => ({
        id: e.id,
        email: e.email,
        is_primary: e.is_primary,
      }));
    }
    // Legacy fallback: providers saved before the multi-email migration.
    if (initialData.email) {
      return [{ email: initialData.email.trim(), is_primary: true }];
    }
    return [];
  });
  const [phoneErrors, setPhoneErrors] = useState<Record<number, string>>({});
  const [emailErrors, setEmailErrors] = useState<Record<number, string>>({});
  const [visitStability, setVisitStability] = useState<string>(
    inv?.initial.visit_stability ?? initialData?.visit_stability ?? 'NOT_STABLE_VISIT'
  );
  const [status, setStatus] = useState<string>(initialData?.status ?? 'ACTIVE');
  const [publication, setPublication] = useState<string>(
    initialData?.publication_status ?? 'UNPUBLISHED'
  );
  // Doctor-only professional info (shown only when providerType === 'DOCTOR')
  const [professionalTitle, setProfessionalTitle] = useState(
    initialData?.doctor_profile?.professional_title ?? ''
  );
  const [yearsExperience, setYearsExperience] = useState(
    initialData?.doctor_profile?.years_experience != null
      ? String(initialData.doctor_profile.years_experience)
      : ''
  );
  const [biography, setBiography] = useState(initialData?.doctor_profile?.biography ?? '');
  const [experienceDescription, setExperienceDescription] = useState(
    initialData?.doctor_profile?.experience_description ?? ''
  );
  const [firstName, setFirstName] = useState(initialData?.doctor_profile?.first_name ?? '');
  const [lastName, setLastName] = useState(initialData?.doctor_profile?.last_name ?? '');
  const [qualifications, setQualifications] = useState<Array<QualificationCreate & { id?: string }>>(
    initialData?.qualifications?.map((q) => ({ id: q.id, title: q.title, institution: q.institution, year_obtained: q.year_obtained, description: q.description, display_order: q.display_order })) ?? []
  );
  const [languages, setLanguages] = useState<Language[]>([]);
  const [languageError, setLanguageError] = useState<string | null>(null);
  const [loadingLanguages, setLoadingLanguages] = useState(true);
  const [selectedLanguageIds, setSelectedLanguageIds] = useState<string[]>(
    initialData?.languages?.map((l) => l.id) ?? []
  );
  const [languageFilter, setLanguageFilter] = useState('');
  const [maximumRadius, setMaximumRadius] = useState(initialData?.maximum_working_radius_km != null ? String(initialData.maximum_working_radius_km) : '');
  const [emergencyServices, setEmergencyServices] = useState(initialData?.emergency_services_available ?? false);
  const [emergencyNumber, setEmergencyNumber] = useState(initialData?.emergency_contact_number ?? '');
  const [photo, setPhoto] = useState<File | null>(null);
  const [photoPreview, setPhotoPreview] = useState<string | null>(initialData?.thumbnail_url ?? null);
  const [savedProviderId, setSavedProviderId] = useState<string | null>(null);
  const [photoError, setPhotoError] = useState<string | null>(null);
  const [selectedSpecIds, setSelectedSpecIds] = useState<string[]>(
    inv?.initial.specialization_ids ?? initialData?.specializations.map((s) => s.id) ?? []
  );

  useEffect(() => () => {
    if (photoPreview?.startsWith('blob:')) URL.revokeObjectURL?.(photoPreview);
  }, [photoPreview]);

  // Location — pre-populate from the existing primary location in edit mode.
  const [location, setLocation] = useState<LocationValues>(() => {
    if (inv) {
      const draftPrimary =
        inv.initial.locations.find((l) => l.is_primary) ?? inv.initial.locations[0];
      if (!draftPrimary) return EMPTY_LOCATION;
      return {
        name: draftPrimary.name ?? '',
        address_line_1: draftPrimary.address_line_1,
        address_line_2: draftPrimary.address_line_2 ?? '',
        city: draftPrimary.city,
        state_province: draftPrimary.state_province ?? '',
        country: draftPrimary.country ?? '',
        postal_code: draftPrimary.postal_code ?? '',
        latitude: draftPrimary.latitude != null ? String(draftPrimary.latitude) : '',
        longitude: draftPrimary.longitude != null ? String(draftPrimary.longitude) : '',
      };
    }
    if (!initialData) return EMPTY_LOCATION;
    const primary =
      initialData.locations.find((l) => l.is_primary) ?? initialData.locations[0];
    if (!primary) return EMPTY_LOCATION;
    return {
      name: primary.name ?? '',
      address_line_1: primary.address_line_1,
      address_line_2: primary.address_line_2 ?? '',
      city: primary.city,
      state_province: primary.state_province ?? '',
      country: primary.country ?? '',
      postal_code: primary.postal_code ?? '',
      latitude: primary.latitude != null ? String(primary.latitude) : '',
      longitude: primary.longitude != null ? String(primary.longitude) : '',
    };
  });
  const [postalCandidates, setPostalCandidates] = useState<PostalCandidate[]>([]);
  const [postalMessage, setPostalMessage] = useState('');
  const [postalLoading, setPostalLoading] = useState(false);
  const [selectedPostalCode, setSelectedPostalCode] = useState<string | null>(initialData?.locations.length ? (initialData.locations.find((l) => l.is_primary) ?? initialData.locations[0]).postal_code ?? null : null);

  const [specializations, setSpecializations] = useState<Specialization[]>([]);
  const [specsError, setSpecsError] = useState<string | null>(null);
  const [loadingSpecializations, setLoadingSpecializations] = useState(true);
  const [specFilter, setSpecFilter] = useState('');

  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [apiError, setApiError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [savingDraft, setSavingDraft] = useState(false);

  // Load active specializations for the multi-select (page through all).
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        let all: Specialization[];
        if (inv) {
          const rows = await inv.loadSpecializations();
          all = rows.map((r) => ({
            id: r.id, name: r.name, description: null, is_active: true, created_at: '', updated_at: '',
          }));
        } else {
          all = [];
          let pageNum = 1;
          for (;;) {
            const res = await listSpecializations({ is_active: true, page: pageNum, page_size: 100 });
            all.push(...res.data);
            if (pageNum >= res.meta.total_pages) break;
            pageNum += 1;
          }
        }
        if (!cancelled) setSpecializations(initialData
          ? [...all, ...initialData.specializations.filter((saved) => !all.some((item) => item.id === saved.id))
            .map((saved) => ({ ...saved, description: null, created_at: '', updated_at: '' }))]
          : all);
      } catch (err) {
        if (!cancelled) setSpecsError(extractErrorMessage(err, 'Failed to load specializations.'));
      } finally {
        if (!cancelled) setLoadingSpecializations(false);
      }
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (inv) return;
    let cancelled = false;
    (async () => {
      try {
        let all: Language[] = [];
        let page = 1;
        for (;;) {
          const result = await listLanguages({ is_active: true, page, page_size: 100 });
          all.push(...result.data);
          if (page >= result.meta.total_pages) break;
          page += 1;
        }
        if (!cancelled) setLanguages(initialData
          ? [...all, ...initialData.languages.filter((saved) => !all.some((item) => item.id === saved.id))]
          : all);
      } catch (err) {
        if (!cancelled) setLanguageError(extractErrorMessage(err, 'Failed to load languages.'));
      } finally {
        if (!cancelled) setLoadingLanguages(false);
      }
    })();
    return () => { cancelled = true; };
  }, [inv]);

  useEffect(() => {
    if (!wizard) return;
    const query = location.postal_code.trim();
    if (query.length < 4 || query === selectedPostalCode) return;
    const controller = new AbortController();
    const timeout = window.setTimeout(async () => {
      setPostalLoading(true);
      try {
        const result = await lookupProviderPostalCode(query, controller.signal);
        if (controller.signal.aborted) return;
        setPostalCandidates(result.candidates);
        setPostalMessage(result.status === 'no_match'
          ? 'No matching place found. Enter the location manually.'
          : result.status === 'unavailable'
            ? 'Lookup is unavailable. Enter the location manually.'
            : 'Choose a place below to fill your location.');
      } catch {
        if (!controller.signal.aborted) {
          setPostalCandidates([]);
          setPostalMessage('Lookup is unavailable. Enter the location manually.');
        }
      } finally {
        if (!controller.signal.aborted) setPostalLoading(false);
      }
    }, 550);
    return () => { controller.abort(); window.clearTimeout(timeout); };
  }, [wizard, location.postal_code, selectedPostalCode]);

  function updatePostalCode(value: string) {
    setLocation((current) => ({
      ...current, postal_code: value, country: '', state_province: '', city: '',
    }));
    setSelectedPostalCode(null);
    setPostalCandidates([]);
    setPostalMessage('');
    setFieldErrors((current) => ({
      ...current, country: '', state_province: '', city: '',
    }));
  }

  function selectPostalCandidate(candidate: PostalCandidate) {
    setLocation((current) => ({
      ...current,
      postal_code: candidate.postal_code || current.postal_code,
      country: Country.getCountryByCode(candidate.country_code?.toUpperCase() ?? '')?.name ?? candidate.country,
      state_province: candidate.state_province || '',
      city: candidate.city,
    }));
    setSelectedPostalCode(candidate.postal_code || location.postal_code);
    setPostalCandidates([]);
    setPostalMessage('Location filled. You can correct it below.');
    setFieldErrors((current) => ({
      ...current, country: '', state_province: '', city: '',
    }));
  }

  function toggleSpec(id: string) {
    setSelectedSpecIds((ids) =>
      ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id]
    );
  }

  function validate(step?: number): boolean {
    const errors: Record<string, string> = {};
    if (!providerType) errors.provider_type = 'Provider type is required.';
    if (!name.trim()) errors.name = 'Name is required.';
    if (!visitStability) errors.visit_stability = 'Visit Stable is required.';
    if (wizard && providerType === 'DOCTOR' && !firstName.trim() &&
      (!isEdit || initialData?.provider_type !== 'DOCTOR' || Boolean(initialData.doctor_profile?.first_name)))
      errors.first_name = 'First name is required.';
    if (wizard && providerType === 'DOCTOR' && !lastName.trim() &&
      (!isEdit || initialData?.provider_type !== 'DOCTOR' || Boolean(initialData.doctor_profile?.last_name)))
      errors.last_name = 'Last name is required.';
    if (providerType === 'DOCTOR' && yearsExperience.trim()) {
      const n = Number(yearsExperience);
      if (!Number.isInteger(n) || n < 0 || n > 100) {
        errors.years_experience = 'Years of experience must be a whole number between 0 and 100.';
      }
    }
    if (!inv && !isEdit && !location.country.trim()) errors.country = 'Country is required.';
    if (!inv && !isEdit && !location.city.trim()) errors.city = 'City is required.';
    if (!inv && !isEdit && !location.address_line_1.trim()) errors.address_line_1 = 'Address is required.';
    if (wizard && !isEdit && !location.postal_code.trim()) errors.postal_code = 'Pincode / postal code is required.';
    const originalLocation = initialData?.locations.find((l) => l.is_primary) ?? initialData?.locations[0];
    const locationChanged = !isEdit || (originalLocation
      ? (Object.keys(location) as (keyof LocationValues)[]).some((key) =>
          location[key].trim() !== String(originalLocation[key] ?? '').trim())
      : Object.values(location).some((value) => value.trim()));
    if (locationChanged && (location.address_line_1.trim() || Object.values(location).some((value) => value.trim())) && !location.city.trim()) {
      errors.city = 'City is required when an address is provided.';
    }
    // New admin providers require a primary email. Legacy edit records may
    // predate contact rows and must remain editable without one.
    if (!inv && !isEdit && !emailEntries.some((e) => e.email.trim() && e.is_primary)) {
      errors.email = 'A primary email is required.';
    }
    if (!inv && visitStability === 'STABLE_VISIT' && (!maximumRadius.trim() || !Number.isFinite(Number(maximumRadius)) || Number(maximumRadius) <= 0) &&
      !(isEdit && initialData?.visit_stability === 'STABLE_VISIT' && initialData.maximum_working_radius_km == null && !maximumRadius.trim())) {
      errors.maximum_working_radius_km = 'A finite radius greater than 0 is required for stable visits.';
    }
    if (!inv && visitStability === 'NOT_STABLE_VISIT' && maximumRadius.trim()) {
      errors.maximum_working_radius_km = 'Radius is only available for stable visits.';
    }
    if (!inv && emergencyServices && !emergencyNumber.trim() &&
      !(isEdit && initialData?.emergency_services_available && !initialData.emergency_contact_number))
      errors.emergency_contact_number = 'Emergency contact number is required.';
    if (!inv && providerType === 'DOCTOR') {
      qualifications.forEach((q, i) => {
        if (!q.title.trim()) errors[`qualification_${i}`] = 'Qualification title is required.';
      });
    }
    if (locationChanged && Object.values(location).some((value) => value.trim()) && !location.address_line_1.trim()) {
      errors.address_line_1 = 'Address line 1 is required when a city is provided.';
    }
    if (locationChanged && isEdit && originalLocation && !location.address_line_1.trim()) {
      errors.address_line_1 = 'Address line 1 cannot be removed from an existing location.';
    }
    // Contact rows are optional, but existing rows must be non-empty.
    const phErrors: Record<number, string> = {};
    phoneEntries.forEach((p, i) => {
      if (!p.number.trim()) phErrors[i] = 'Enter a number or remove this row.';
    });
    const emErrors: Record<number, string> = {};
    emailEntries.forEach((e, i) => {
      if (!e.email.trim()) emErrors[i] = 'Enter an email or remove this row.';
      else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(e.email.trim())) emErrors[i] = 'Enter a valid email address.';
    });
    const visibleErrors = Object.fromEntries(
      Object.entries(errors).filter(([key]) => step === undefined || wizardStepForField(key) === step)
    );
    const contactStep = step === undefined || step === 3;
    setPhoneErrors(contactStep ? phErrors : {});
    setEmailErrors(contactStep ? emErrors : {});
    setFieldErrors(visibleErrors);
    const valid = Object.keys(visibleErrors).length === 0 &&
      (!contactStep || (Object.keys(phErrors).length === 0 && Object.keys(emErrors).length === 0));
    if (!valid && step === undefined && wizard) {
      setWizardStep(Math.min(
        ...Object.keys(errors).map(wizardStepForField),
        ...(Object.keys(phErrors).length || Object.keys(emErrors).length ? [3] : []),
      ));
    }
    return valid;
  }

  function nextWizardStep() {
    if (!validate(wizardStep)) return;
    const nextStep = stepOrder[Math.min(wizardPosition + 1, stepOrder.length - 1)];
    if (nextStep === WIZARD_STEPS.length - 1) setReviewReady(false);
    setWizardStep(nextStep);
  }

  useEffect(() => {
    if (!wizard || wizardStep !== WIZARD_STEPS.length - 1 || savedProviderId) return;
    // The next physical click in a double-click can land on the newly rendered CTA.
    const timer = window.setTimeout(() => setReviewReady(true), 500);
    return () => window.clearTimeout(timer);
  }, [wizard, wizardStep, savedProviderId]);

  function buildInvitationPayload(): InvitationDraftPayload {
    const payload: InvitationDraftPayload = {
      description: description.trim() || null,
      website: website.trim() || null,
      specialization_ids: selectedSpecIds,
      phones: phoneEntries
        .filter((p) => p.number.trim())
        .map((p) => ({
          country_code: p.country_code,
          number: p.number.trim(),
          is_primary: p.is_primary,
        })),
      emails: emailEntries
        .filter((e) => e.email.trim())
        .map((e) => ({ email: e.email.trim(), is_primary: e.is_primary })),
    };
    if (name.trim()) payload.name = name.trim();
    if (visitStability) payload.visit_stability = visitStability as VisitStability;
    if (location.address_line_1.trim() && location.city.trim()) {
      payload.locations = [
        {
          name: location.name.trim() || null,
          address_line_1: location.address_line_1.trim(),
          address_line_2: location.address_line_2.trim() || null,
          city: location.city.trim(),
          state_province: location.state_province.trim() || null,
          country: location.country.trim() || null,
          postal_code: location.postal_code.trim() || null,
          latitude: location.latitude.trim() ? parseFloat(location.latitude) : null,
          longitude: location.longitude.trim() ? parseFloat(location.longitude) : null,
          is_primary: true,
        },
      ];
    }
    return payload;
  }

  async function handleSaveDraft() {
    if (!inv) return;
    setApiError(null);
    setSavingDraft(true);
    try {
      await inv.onSaveDraft(buildInvitationPayload());
    } catch (err) {
      setApiError(extractErrorMessage(err, 'Failed to save your draft. Please try again.'));
    } finally {
      setSavingDraft(false);
    }
  }

  async function retryPhotoUpload() {
    if (!photo || !savedProviderId || submissionInProgress.current) return;
    submissionInProgress.current = true;
    setSubmitting(true);
    setPhotoError(null);
    try {
      await uploadProviderPhoto(savedProviderId, photo, { display_order: 0, is_thumbnail: true });
      const refreshed = await getProvider(savedProviderId);
      setSavedProviderId(null);
      setPhoto(null);
      submissionCompleted.current = true;
      onSuccess?.(refreshed);
    } catch (err) {
      setPhotoError(`Provider saved, but the photo could not be uploaded. Please retry or edit provider ${savedProviderId}: ${extractErrorMessage(err, 'upload failed')}`);
    } finally {
      submissionInProgress.current = false;
      setSubmitting(false);
    }
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    // Wizard navigation and creation are explicit button actions, never an
    // implicit form submit (including Enter or a click's native default).
    if (wizard) return;
    void submitProvider();
  }

  async function submitProvider() {
    if (submissionInProgress.current || submissionCompleted.current || (wizard && (wizardStep !== WIZARD_STEPS.length - 1 || !reviewReady))) return;
    setApiError(null);
    if (!validate()) return;

    if (inv) {
      setSubmitting(true);
      try {
        await inv.onSubmit(buildInvitationPayload());
      } catch (err) {
        setApiError(extractErrorMessage(err, 'Failed to submit. Please check the form and try again.'));
      } finally {
        setSubmitting(false);
      }
      return;
    }

    // A provider was already persisted when only its photo upload failed.
    // Never submit the core form again (which could create a duplicate).
    if (savedProviderId && photo) {
      await retryPhotoUpload();
      return;
    }

    submissionInProgress.current = true;
    setSubmitting(true);
    setPhotoError(null);
    try {
      let saved: Provider;
      if (isEdit && initialData) {
        saved = await updateProvider(initialData.id, {
          admin_form_version: 2,
          provider_type: providerType as ProviderType,
          name: name.trim(),
          description: description.trim() || null,
          website: website.trim() || null,
          ...(initialData.visit_stability === 'STABLE_VISIT' && initialData.maximum_working_radius_km == null &&
            visitStability === 'STABLE_VISIT' && !maximumRadius.trim()
            ? {} : {
              visit_stability: visitStability as VisitStability,
              maximum_working_radius_km: visitStability === 'STABLE_VISIT' && maximumRadius.trim() ? Number(maximumRadius) : null,
            }),
          first_name: providerType === 'DOCTOR' ? firstName.trim() || null : null,
          last_name: providerType === 'DOCTOR' ? lastName.trim() || null : null,
          ...(selectedLanguageIds.length !== initialData.languages.length ||
            selectedLanguageIds.some((id) => !initialData.languages.some((language) => language.id === id))
            ? { language_ids: selectedLanguageIds } : {}),
          ...(emergencyServices !== Boolean(initialData.emergency_services_available) ||
            emergencyNumber !== (initialData.emergency_contact_number ?? '')
            ? {
                emergency_services_available: emergencyServices,
                emergency_contact_number: emergencyServices ? emergencyNumber.trim() || null : null,
              } : {}),
          ...(providerType === 'DOCTOR'
            ? {
                professional_title: professionalTitle.trim() || null,
                years_experience: yearsExperience.trim() ? Number(yearsExperience) : null,
                biography: biography.trim() || null,
                experience_description: experienceDescription.trim() || null,
                qualifications: qualifications.map((q, i) => ({
                  ...q,
                  title: q.title.trim(),
                  institution: q.institution?.trim() || null,
                  description: q.description?.trim() || null,
                  display_order: i,
                })),
              }
            : {}),
        });
        // Status / publication use dedicated endpoints — only when changed.
        if (status !== initialData.status) {
          saved = await updateProviderStatus(initialData.id, status as ProviderStatus);
        }
        if (publication !== initialData.publication_status) {
          saved = await updateProviderPublication(
            initialData.id,
            publication as PublicationStatus
          );
        }
        // Specializations: apply the diff; untouched relationships persist.
        const originalIds = initialData.specializations.map((s) => s.id);
        const toAdd = selectedSpecIds.filter((id) => !originalIds.includes(id));
        const toRemove = originalIds.filter((id) => !selectedSpecIds.includes(id));
        for (const specId of toAdd) {
          saved = await addProviderSpecialization(initialData.id, specId);
        }
        for (const specId of toRemove) {
          saved = await removeProviderSpecialization(initialData.id, specId);
        }
        // Phones: diff against the saved list. Changed rows are re-created.
        const keptPhoneIds = new Set<string>();
        const phonesToAdd: PhoneEntry[] = [];
        for (const entry of phoneEntries) {
          const original = entry.id
            ? initialData.phones.find((p) => p.id === entry.id)
            : undefined;
          const unchanged =
            original &&
            original.country_code === entry.country_code &&
            original.number === entry.number.trim() &&
            original.is_primary === entry.is_primary;
          if (unchanged && entry.id) {
            keptPhoneIds.add(entry.id);
          } else {
            phonesToAdd.push(entry);
          }
        }
        const phonesToRemove = initialData.phones.filter((p) => !keptPhoneIds.has(p.id));
        for (const p of phonesToRemove) {
          await removeProviderPhone(initialData.id, p.id);
        }
        for (const entry of phonesToAdd) {
          await addProviderPhone(initialData.id, {
            country_code: entry.country_code,
            number: entry.number.trim(),
            is_primary: entry.is_primary,
          });
        }
        // Emails: same diff approach.
        const keptEmailIds = new Set<string>();
        const emailsToAdd: EmailEntry[] = [];
        for (const entry of emailEntries) {
          const original = entry.id
            ? initialData.emails.find((e) => e.id === entry.id)
            : undefined;
          const unchanged =
            original &&
            original.email === entry.email.trim() &&
            original.is_primary === entry.is_primary;
          if (unchanged && entry.id) {
            keptEmailIds.add(entry.id);
          } else {
            emailsToAdd.push(entry);
          }
        }
        const emailsToRemove = initialData.emails.filter((e) => !keptEmailIds.has(e.id));
        for (const e of emailsToRemove) {
          await removeProviderEmail(initialData.id, e.id);
        }
        for (const entry of emailsToAdd) {
          await addProviderEmail(initialData.id, {
            email: entry.email.trim(),
            is_primary: entry.is_primary,
          });
        }

        // Location: PATCH existing primary, or POST a new one when filled.
        const locationFilled =
          location.address_line_1.trim() && location.city.trim();
        const originalLocation =
          initialData.locations.find((l) => l.is_primary) ?? initialData.locations[0];
        const locationChanged = originalLocation
          ? (Object.keys(location) as (keyof LocationValues)[]).some((key) =>
              location[key].trim() !== String(originalLocation[key] ?? '').trim())
          : Object.values(location).some((value) => value.trim());
        if (locationFilled && locationChanged) {
          const locBody = {
            name: location.name.trim() || null,
            address_line_1: location.address_line_1.trim(),
            address_line_2: location.address_line_2.trim() || null,
            city: location.city.trim(),
            state_province: location.state_province.trim() || null,
            country: location.country.trim() || null,
            postal_code: location.postal_code.trim() || null,
            latitude: location.latitude.trim() ? parseFloat(location.latitude) : null,
            longitude: location.longitude.trim() ? parseFloat(location.longitude) : null,
            is_primary: true,
          };
          if (originalLocation) {
            await updateProviderLocation(initialData.id, originalLocation.id, locBody);
          } else {
            await createProviderLocation(initialData.id, locBody);
          }
        }

        // Re-read after relationship/qualification updates so the detail view
        // receives the same shape as a freshly loaded provider.
        saved = await getProvider(initialData.id);
      } else {
        let primary_location: ProviderLocationCreate | null = null;
        if (location.address_line_1.trim() && location.city.trim()) {
          primary_location = {
            name: location.name.trim() || null,
            address_line_1: location.address_line_1.trim(),
            address_line_2: location.address_line_2.trim() || null,
            city: location.city.trim(),
            state_province: location.state_province.trim() || null,
            country: location.country.trim() || null,
            postal_code: location.postal_code.trim() || null,
            latitude: location.latitude.trim() ? parseFloat(location.latitude) : null,
            longitude: location.longitude.trim() ? parseFloat(location.longitude) : null,
            is_primary: true,
          };
        }
        const body: ProviderCreate = {
          admin_form_version: 2,
          provider_type: providerType as ProviderType,
          name: name.trim(),
          visit_stability: visitStability as VisitStability,
          description: description.trim() || null,
          website: website.trim() || null,
          status: status as ProviderStatus,
          publication_status: publication as PublicationStatus,
          specialization_ids: selectedSpecIds,
          language_ids: selectedLanguageIds,
          maximum_working_radius_km: visitStability === 'STABLE_VISIT' && maximumRadius.trim() ? Number(maximumRadius) : null,
          emergency_services_available: emergencyServices,
          emergency_contact_number: emergencyServices ? emergencyNumber.trim() || null : null,
          primary_location,
          phones: phoneEntries.map((p) => ({
            country_code: p.country_code,
            number: p.number.trim(),
            is_primary: p.is_primary,
          })),
          emails: emailEntries.map((e) => ({
            email: e.email.trim(),
            is_primary: e.is_primary,
          })),
          ...(providerType === 'DOCTOR'
            ? {
                professional_title: professionalTitle.trim() || null,
                years_experience: yearsExperience.trim() ? Number(yearsExperience) : null,
                biography: biography.trim() || null,
                experience_description: experienceDescription.trim() || null,
                first_name: firstName.trim() || null,
                last_name: lastName.trim() || null,
                qualifications: qualifications.map((q, i) => ({
                  ...q,
                  title: q.title.trim(),
                  institution: q.institution?.trim() || null,
                  description: q.description?.trim() || null,
                  display_order: i,
                })),
              }
            : {}),
        };
        saved = await createProvider(body);
      }
      if (photo) {
        try {
          const uploaded = await uploadProviderPhoto(saved.id, photo, {
            display_order: 0,
            is_thumbnail: true,
          });
          saved = { ...saved, photos: [...saved.photos, uploaded], thumbnail_url: saved.thumbnail_url };
        } catch (photoErr) {
          setSavedProviderId(saved.id);
          setPhotoError(`Provider saved, but the photo could not be uploaded. Please retry or edit provider ${saved.id}: ${extractErrorMessage(photoErr, 'upload failed')}`);
          return;
        }
      }
      setSavedProviderId(null);
      submissionCompleted.current = true;
      onSuccess?.(saved);
    } catch (err) {
      setApiError(extractErrorMessage(err, 'Failed to save provider. Please try again.'));
    } finally {
      submissionInProgress.current = false;
      setSubmitting(false);
    }
  }

  const errs = { ...fieldErrors, ...(inv?.externalErrors ?? {}) };

  return (
    <form onSubmit={handleSubmit} noValidate className={styles.form}>
      {wizard && (
        <ProviderWizardHeader
          steps={stepOrder.map((index) => index === 4 && isEdit
            ? { title: 'Review & save', description: 'Check everything before saving your changes.' }
            : WIZARD_STEPS[index])}
          mode={isEdit ? 'edit' : 'add'}
          current={wizardPosition}
          onSelect={(index) => setWizardStep(stepOrder[index])}
          locked={Boolean(savedProviderId) || submitting}
        />
      )}
      {(apiError || photoError || errs._form) && (
        <div className={`${styles.apiError} ${styles.cardFull}`} role="alert">
          {apiError ?? photoError ?? errs._form}
          {photoError && savedProviderId && (
            <>
              <Button type="button" variant="secondary" onClick={retryPhotoUpload} disabled={submitting}>Retry photo upload</Button>
              <Link to={`/admin/providers/${savedProviderId}/edit`}>Edit saved provider</Link>
            </>
          )}
        </div>
      )}

      {/* ── Basic information ─────────────────────────────────────────────── */}
      {(!wizard || wizardStep === 0) && <Card padding="lg" shadow="sm" className={wizard ? `${styles.cardFull} ${styles.dropdownCard}` : undefined}>
        <section className={styles.section}>
          <h3 className={styles.sectionTitle}>Basic information</h3>
          <div className={styles.grid}>
            <Select
              label="Provider type"
              options={PROVIDER_TYPE_OPTIONS}
              placeholder="Select type…"
              value={providerType}
              onChange={(e) => setProviderType(e.target.value)}
              error={errs.provider_type}
              disabled={Boolean(inv)}
              required
            />
            <Input
              label={inv ? 'Name' : 'Provider / practice name'}
              placeholder="e.g. St. Mary's Hospital"
              value={name}
              onChange={(e) => setName(e.target.value)}
              error={errs.name}
              required
              maxLength={300}
            />
          </div>

          <FormField label="Description" optional htmlFor="provider-desc">
            <textarea
              id="provider-desc"
              className={styles.textarea}
              placeholder="Brief description of this provider…"
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </FormField>

          <Input
            label="Website"
            type="url"
            placeholder="https://example.com"
            value={website}
            onChange={(e) => setWebsite(e.target.value)}
          />
          {wizard && (
            <div className={styles.basicSelections}>
              <SignupMultiSelect
                tone="light"
                label="Specializations"
                options={specializations}
                selectedIds={selectedSpecIds}
                onChange={setSelectedSpecIds}
                loading={loadingSpecializations}
                error={specsError ?? undefined}
              />
              <SignupMultiSelect
                tone="light"
                label="Languages"
                options={languages}
                selectedIds={selectedLanguageIds}
                onChange={setSelectedLanguageIds}
                loading={loadingLanguages}
                error={languageError ?? undefined}
              />
            </div>
          )}
          {!inv && (
            <FormField label="Profile photo" optional htmlFor="provider-photo">
              <input id="provider-photo" className={styles.photoInput} type="file" accept="image/jpeg,image/png,image/gif,image/webp" onChange={(e) => {
                const file = e.target.files?.[0] ?? null;
                if (file && (!['image/jpeg', 'image/png', 'image/gif', 'image/webp'].includes(file.type) || file.size > 10 * 1024 * 1024)) {
                  setPhoto(null);
                  setPhotoError('Choose a JPEG, PNG, GIF, or WebP image under 10 MB.');
                  e.target.value = '';
                  return;
                }
                setPhotoError(null);
                setPhoto(file);
                if (file) setPhotoPreview(URL.createObjectURL(file));
              }} />
              <label htmlFor="provider-photo" className={styles.photoDropzone}>
                {photoPreview
                  ? <img className={styles.photoPreview} src={photoPreview} alt="Profile preview" />
                  : <span className={styles.photoIcon} aria-hidden="true">↑</span>}
                <span className={styles.photoCopy}>
                  <strong>{photo?.name ?? (photoPreview ? 'Change profile photo' : 'Choose a profile photo')}</strong>
                  <small>JPEG, PNG, GIF, or WebP · up to 10 MB</small>
                </span>
                <span className={styles.photoAction}>Browse files</span>
              </label>
            </FormField>
          )}
        </section>
      </Card>}

      {/* ── Contact ───────────────────────────────────────────────────────── */}
      {(!wizard || wizardStep === 3) && <Card padding="lg" shadow="sm" className={wizard ? styles.cardFull : undefined}>
        <section className={styles.section}>
          <h3 className={styles.sectionTitle}>Contact information {inv && <span className={styles.optionalTag}>— optional</span>}</h3>
          {!inv && !isEdit && <p className={styles.hint}>Add at least one primary email address. Phone is optional.</p>}
          {errs.email && <p className={styles.fieldError} role="alert">{errs.email}</p>}
          <MultiPhoneField
            entries={phoneEntries}
            onChange={(next) => { setPhoneEntries(next); setPhoneErrors({}); }}
            errors={phoneErrors}
            disabled={submitting}
          />
          <MultiEmailField
            entries={emailEntries}
            onChange={(next) => { setEmailEntries(next); setEmailErrors({}); }}
            errors={emailErrors}
            disabled={submitting}
          />
        </section>
      </Card>}

      {/* ── Professional info — doctors only ─────────────────────────────── */}
      {!inv && providerType === 'DOCTOR' && (!wizard || wizardStep === 1) && (
        <Card padding="lg" shadow="sm" className={styles.cardFull}>
          <section className={styles.section}>
            <h3 className={styles.sectionTitle}>
              Professional info <span className={styles.optionalTag}>— optional</span>
            </h3>
            <div className={styles.grid}>
              <Input label="First name" value={firstName} onChange={(e) => setFirstName(e.target.value)} error={errs.first_name} required={!isEdit} />
              <Input label="Last name" value={lastName} onChange={(e) => setLastName(e.target.value)} error={errs.last_name} required={!isEdit} />
              <Input
                label="Professional title"
                placeholder="e.g. Consultant Cardiologist"
                value={professionalTitle}
                onChange={(e) => setProfessionalTitle(e.target.value)}
                maxLength={200}
              />
              <Input
                label="Years of experience"
                type="number"
                min={0}
                max={100}
                placeholder="0 to 100"
                value={yearsExperience}
                onChange={(e) => setYearsExperience(e.target.value)}
                error={errs.years_experience}
              />
            </div>
            <FormField label="Biography" optional htmlFor="doctor-biography">
              <textarea
                id="doctor-biography"
                className={styles.textarea}
                placeholder="Professional background, education, achievements…"
                rows={4}
                maxLength={10000}
                value={biography}
                onChange={(e) => setBiography(e.target.value)}
              />
            </FormField>
            <FormField label="Experience notes" optional htmlFor="doctor-experience">
              <textarea
                id="doctor-experience"
                className={styles.textarea}
                placeholder="Notable experience, previous positions…"
                rows={3}
                maxLength={5000}
                value={experienceDescription}
                onChange={(e) => setExperienceDescription(e.target.value)}
              />
            </FormField>
            <div className={styles.qualificationHeader}>
              <strong>Qualifications</strong>
              <Button type="button" variant="secondary" onClick={() => setQualifications((q) => [...q, { title: '', display_order: q.length }])}>Add qualification</Button>
            </div>
            {qualifications.map((q, i) => (
              <div className={styles.qualificationRow} key={`qualification-${i}`}>
                <Input label="Title" value={q.title} onChange={(e) => setQualifications((all) => all.map((x, j) => j === i ? { ...x, title: e.target.value } : x))} error={errs[`qualification_${i}`]} required />
                <Input label="Institution" value={q.institution ?? ''} onChange={(e) => setQualifications((all) => all.map((x, j) => j === i ? { ...x, institution: e.target.value } : x))} />
                <Input label="Year" type="number" value={q.year_obtained ?? ''} onChange={(e) => setQualifications((all) => all.map((x, j) => j === i ? { ...x, year_obtained: e.target.value ? Number(e.target.value) : null } : x))} />
                <Button type="button" variant="ghost" onClick={() => setQualifications((all) => all.filter((_, j) => j !== i))}>Remove</Button>
              </div>
            ))}
          </section>
        </Card>
      )}

      {/* ── Specializations ───────────────────────────────────────────────── */}
      {!wizard && <Card padding="lg" shadow="sm" className={styles.cardFull}>
        <section className={styles.section}>
          <h3 className={styles.sectionTitle}>
            Specializations
            {selectedSpecIds.length > 0 && (
              <span className={styles.specCountBadge}>{selectedSpecIds.length} selected</span>
            )}
          </h3>
          {specsError && <p className={styles.fieldError} role="alert">{specsError}</p>}
          {!specsError && specializations.length === 0 && (
            <p className={styles.hint}>No active specializations available.</p>
          )}
          {specializations.length >= 8 && (
            <input
              type="text"
              className={styles.specFilterInput}
              placeholder="Filter specializations…"
              value={specFilter}
              onChange={(e) => setSpecFilter(e.target.value)}
            />
          )}
          {(() => {
            if (!specFilter) return null;
            const hiddenSelected = selectedSpecIds.filter(
              (id) => !specializations
                .filter((s) => s.name.toLowerCase().includes(specFilter.toLowerCase()))
                .some((s) => s.id === id)
            ).length;
            return hiddenSelected > 0 ? (
              <p className={styles.specHiddenHint}>
                {hiddenSelected} selected not shown — clear filter to see {hiddenSelected === 1 ? 'it' : 'them'}
              </p>
            ) : null;
          })()}
          <div className={styles.specChipGrid}>
            {specializations
              .filter((spec) =>
                spec.name.toLowerCase().includes(specFilter.toLowerCase())
              )
              .map((spec) => {
                const selected = selectedSpecIds.includes(spec.id);
                return (
                  <button
                    key={spec.id}
                    type="button"
                    className={`${styles.specChip}${selected ? ` ${styles.specChipSelected}` : ''}`}
                    onClick={() => toggleSpec(spec.id)}
                  >
                    {selected && <span className={styles.specChipCheck}>✓</span>}
                    {spec.name}
                  </button>
                );
              })}
          </div>
        </section>
      </Card>}

      {!inv && !wizard && <Card padding="lg" shadow="sm" className={styles.cardFull}>
        <section className={styles.section}>
          <h3 className={styles.sectionTitle}>Languages</h3>
          {languageError && <p className={styles.fieldError} role="alert">{languageError}</p>}
           <input className={styles.specFilterInput} placeholder="Search languages…" aria-label="Search languages" value={languageFilter} onChange={(e) => setLanguageFilter(e.target.value)} />
           <div className={styles.specChipGrid}>{languages.filter((l) => `${l.name} ${l.code}`.toLowerCase().includes(languageFilter.toLowerCase())).map((language) => {
            const selected = selectedLanguageIds.includes(language.id);
             return <button type="button" key={language.id} aria-pressed={selected} className={`${styles.specChip}${selected ? ` ${styles.specChipSelected}` : ''}`} onClick={() => setSelectedLanguageIds((ids) => selected ? ids.filter((id) => id !== language.id) : [...ids, language.id])}>{selected && '✓ '}{language.name} ({language.code})</button>;
          })}</div>
        </section>
      </Card>}

      {/* ── Classification ────────────────────────────────────────────────── */}
      {(!wizard || wizardStep === 2) && <Card padding="lg" shadow="sm" className={wizard ? styles.cardFull : undefined}>
        <section className={styles.section}>
          <h3 className={styles.sectionTitle}>{inv ? 'Classification' : 'Services, status & publication'}</h3>
          <div className={wizard ? styles.serviceLayout : styles.grid}>
            {wizard ? (
              <>
                <div className={styles.serviceRow}>
                  <label className={styles.serviceChoice}>
                    <input type="checkbox" checked={visitStability === 'STABLE_VISIT'} onChange={(e) => {
                      setVisitStability(e.target.checked ? 'STABLE_VISIT' : 'NOT_STABLE_VISIT');
                      if (!e.target.checked) setMaximumRadius('');
                    }} />
                    <span><strong>Stable visit</strong><small>Offer visits at a stable or home location.</small></span>
                  </label>
                  {visitStability === 'STABLE_VISIT' && (
                    <div className={styles.serviceField}>
                      <Input label="Maximum working radius (km)" type="number" min={0.01} step="any"
                        value={maximumRadius} onChange={(e) => setMaximumRadius(e.target.value)}
                        error={errs.maximum_working_radius_km} required />
                      <p className={styles.hint}>Maximum travel distance from the provider's registered location for a stable or home visit.</p>
                    </div>
                  )}
                </div>
                <div className={styles.serviceRow}>
                  <label className={styles.serviceChoice}>
                    <input type="checkbox" checked={emergencyServices} onChange={(e) => setEmergencyServices(e.target.checked)} />
                    <span><strong>Emergency services available</strong><small>Add a number people can call for emergency care.</small></span>
                  </label>
                  {emergencyServices && <Input label="Emergency contact number" type="tel" value={emergencyNumber}
                    onChange={(e) => setEmergencyNumber(e.target.value)} error={errs.emergency_contact_number}
                    required={!isEdit || !initialData?.emergency_services_available || Boolean(initialData.emergency_contact_number)} />}
                </div>
              </>
            ) : (
              <>
                <Select
                  label={inv ? 'Visit Stable' : 'Stable visit'}
                  options={visitStabilityOptions}
                  placeholder="Select…"
                  value={visitStability}
                  onChange={(e) => setVisitStability(e.target.value)}
                  error={errs.visit_stability}
                  required
                />
                {!inv && <div className={styles.serviceFields}>
                  {visitStability === 'STABLE_VISIT' && <><Input label="Maximum working radius (km)" type="number" min={0.01} step="any" value={maximumRadius} onChange={(e) => setMaximumRadius(e.target.value)} error={errs.maximum_working_radius_km} required /><p className={styles.hint}>Maximum travel distance from the provider's registered location for a stable or home visit.</p></>}
                  <label><input type="checkbox" checked={emergencyServices} onChange={(e) => setEmergencyServices(e.target.checked)} /> Emergency services available</label>
                  {emergencyServices && <Input label="Emergency contact number" value={emergencyNumber} onChange={(e) => setEmergencyNumber(e.target.value)} error={errs.emergency_contact_number} required />}
                </div>}
              </>
            )}
            {!inv && (
              <div className={styles.statusRow}>
                <Select
                  label="Status"
                  options={STATUS_OPTIONS}
                  value={status}
                  onChange={(e) => setStatus(e.target.value)}
                />
                <Select
                  label="Publication status"
                  options={PUBLICATION_OPTIONS}
                  value={publication}
                  onChange={(e) => setPublication(e.target.value)}
                />
              </div>
            )}
          </div>
        </section>
      </Card>}

      {/* ── Primary location — shown in both Add and Edit ─────────────────── */}
      {(!wizard || wizardStep === 3) && <Card padding="lg" shadow="sm" className={`${wizard ? styles.cardFull : ''} ${styles.dropdownCard}`}>
        <section className={styles.section}>
          <h3 className={styles.sectionTitle}>
            Provider location {isEdit && <span className={styles.optionalTag}>— existing records may be incomplete</span>}
          </h3>
          <div className={styles.grid}>
            {!inv && <Input
              label="Location name"
              placeholder="e.g. Main Branch, Ward 3…"
              value={location.name}
              onChange={(e) => setLocation((l) => ({ ...l, name: e.target.value }))}
            />}
            <Input
              label={wizard ? 'Address line 1' : 'Address'}
              value={location.address_line_1}
              onChange={(e) => setLocation((l) => ({ ...l, address_line_1: e.target.value }))}
              error={errs.address_line_1}
              required={!isEdit}
            />
            <Input
              label="Address line 2"
              value={location.address_line_2}
              onChange={(e) => setLocation((l) => ({ ...l, address_line_2: e.target.value }))}
            />
            {wizard && (
              <div className={styles.postalLookup}>
                <Input
                  label="Pincode / postal code"
                  autoComplete="postal-code"
                  maxLength={32}
                  value={location.postal_code}
                  onChange={(e) => updatePostalCode(e.target.value)}
                  error={errs.postal_code}
                  required={!isEdit}
                />
                {postalLoading && <p className={styles.hint} role="status">Looking up locations…</p>}
                {!postalLoading && postalMessage && <p className={styles.hint} role="status">{postalMessage}</p>}
                {postalCandidates.length > 0 && (
                  <div className={styles.postalResults} aria-label="Matching postal locations">
                    {postalCandidates.map((candidate, index) => (
                      <button type="button" className={styles.postalResult}
                        key={`${candidate.postal_code}-${candidate.country}-${candidate.city}-${index}`}
                        onClick={() => selectPostalCandidate(candidate)}>
                        {candidate.display_name || [candidate.city, candidate.state_province, candidate.country].filter(Boolean).join(', ')}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
            <LocationPicker
              value={location}
              onChange={(nextLocation) => setLocation((current) => ({ ...current, ...nextLocation }))}
              errors={{
                country: errs.country,
                state_province: errs.state_province,
                city: errs.city,
              }}
              idPrefix="provider-primary-location"
              className={styles.locationPicker}
              required={!inv && !isEdit}
              optionalState
            />
            {!wizard && <Input
              label="Postal code"
              value={location.postal_code}
              onChange={(e) => setLocation((l) => ({ ...l, postal_code: e.target.value }))}
            />}
            <Input
              label="Latitude"
              type="number"
              placeholder="-90 to 90"
              value={location.latitude}
              onChange={(e) => setLocation((l) => ({ ...l, latitude: e.target.value }))}
            />
            <Input
              label="Longitude"
              type="number"
              placeholder="-180 to 180"
              value={location.longitude}
              onChange={(e) => setLocation((l) => ({ ...l, longitude: e.target.value }))}
            />
          </div>
        </section>
      </Card>}

      {wizard && wizardStep === 4 && (
        <ProviderWizardReview
          locked={Boolean(savedProviderId)}
          onEdit={setWizardStep}
          sections={[
            { title: 'Basic details', step: 0, items: [
              { label: 'Provider type', value: PROVIDER_TYPE_OPTIONS.find((option) => option.value === providerType)?.label ?? '' },
              { label: 'Name', value: name.trim() },
              { label: 'Website', value: website.trim() },
              { label: 'Photo', value: photoPreview
                ? <img className={wizardStyles.reviewPhoto} src={photoPreview} alt={photo ? `Selected profile photo: ${photo.name}` : 'Current provider profile photo'} />
                : 'No photo selected' },
              { label: 'Specializations', value: selectedSpecIds.map((id) => specializations.find((s) => s.id === id)?.name ?? initialData?.specializations.find((s) => s.id === id)?.name ?? id).join(', ') },
              { label: 'Languages', value: selectedLanguageIds.map((id) => languages.find((l) => l.id === id)?.name ?? initialData?.languages.find((l) => l.id === id)?.name ?? id).join(', ') },
            ] },
            ...(providerType === 'DOCTOR' ? [{ title: 'Professional details', step: 1, items: [
                { label: 'Doctor / Vet', value: [firstName, lastName].filter(Boolean).join(' ') },
                { label: 'Qualifications', value: qualifications.length ? (
                  <ul className={wizardStyles.reviewQualifications}>
                    {qualifications.map((q, i) => (
                      <li key={q.id ?? i}>
                        <strong>{q.title.trim()}</strong>
                        {(q.institution?.trim() || q.year_obtained != null) && (
                          <span>{[q.institution?.trim(), q.year_obtained].filter((value) => value != null && value !== '').join(' · ')}</span>
                        )}
                      </li>
                    ))}
                  </ul>
                ) : '—' },
            ] }] : []),
            { title: 'Services', step: 2, items: [
              { label: 'Stable visit', value: visitStability === 'STABLE_VISIT' ? 'Yes' : 'No' },
              { label: 'Working radius', value: visitStability === 'STABLE_VISIT' ? `${maximumRadius} km` : 'Not applicable' },
              { label: 'Emergency services', value: emergencyServices ? 'Yes' : 'No' },
              ...(emergencyServices ? [{ label: 'Emergency contact number', value: emergencyNumber }] : []),
              { label: 'Status', value: status },
              { label: 'Publication', value: publication },
            ] },
            { title: 'Contact & location', step: 3, items: [
              { label: 'Email', value: emailEntries.map((e) => e.email.trim()).filter(Boolean).join(', ') },
              { label: 'Phone', value: phoneEntries.map((p) => `${p.country_code} ${p.number.trim()}`).join(', ') },
              { label: 'Location name', value: location.name },
              { label: 'Address', value: [location.address_line_1, location.city, location.state_province, location.country].filter(Boolean).join(', ') },
              { label: 'Pincode / postal code', value: location.postal_code },
            ] },
          ]}
        />
      )}

      <footer className={`${styles.footer} ${styles.cardFull}`}>
        {wizard ? (
          <>
            <Button type="button" variant="ghost" onClick={onCancel} disabled={submitting} className={styles.cancelButton}>Cancel</Button>
            {wizardPosition > 0 && (
              <Button type="button" variant="secondary" onClick={() => setWizardStep(stepOrder[wizardPosition - 1])} disabled={submitting || Boolean(savedProviderId)}>Back</Button>
            )}
            {wizardStep < WIZARD_STEPS.length - 1 ? (
              <Button key="continue" type="button" variant="primary" onClick={nextWizardStep}>Continue</Button>
            ) : (
              <Button key="confirm" type="button" variant="primary" onClick={savedProviderId ? retryPhotoUpload : submitProvider}
                disabled={!savedProviderId && !reviewReady} loading={submitting}>{savedProviderId ? 'Retry photo upload' : isEdit ? 'Save changes' : 'Create provider'}</Button>
            )}
          </>
        ) : inv ? (
          <>
            <Button
              type="button"
              variant="secondary"
              onClick={handleSaveDraft}
              loading={savingDraft}
              disabled={submitting}
            >
              Save draft
            </Button>
            <Button type="submit" variant="primary" loading={submitting} disabled={savingDraft}>
              Submit for review
            </Button>
          </>
        ) : (
          <>
            <Button type="button" variant="ghost" onClick={onCancel} disabled={submitting}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" loading={submitting}>
              {isEdit ? 'Save changes' : 'Create provider'}
            </Button>
          </>
        )}
      </footer>
    </form>
  );
}
