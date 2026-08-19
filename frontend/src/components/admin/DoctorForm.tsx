/**
 * DoctorForm — shared create / edit form for doctors.
 *
 * Props:
 *   initialData — pre-populate when editing (undefined = create mode)
 *   onSuccess(doctor) — called with the saved DoctorResponse on success
 *   onCancel() — called when the user dismisses
 */
import { useEffect, useState } from 'react';
import { extractErrorMessage } from '@/api/client';
import {
  addDoctorSpecialization,
  createDoctor,
  getDoctor,
  removeDoctorSpecialization,
  updateDoctor,
  updateDoctorPublication,
  updateDoctorStatus,
} from '@/api/doctors';
import {
  addProviderEmail,
  addProviderPhone,
  removeProviderEmail,
  removeProviderPhone,
} from '@/api/providers';
import { listSpecializations } from '@/api/specializations';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { FormField } from '@/components/ui/FormField';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { MultiEmailField, type EmailEntry } from './MultiEmailField';
import { MultiPhoneField, type PhoneEntry } from './MultiPhoneField';
import type {
  DoctorCreate,
  DoctorResponse,
  DoctorUpdate,
  ProviderStatus,
  PublicationStatus,
  Specialization,
  VisitStability,
} from '@/types';
import styles from './DoctorForm.module.css';

const VISIT_STABILITY_OPTIONS = [
  { value: 'STABLE_VISIT', label: 'Stable visit' },
  { value: 'NOT_STABLE_VISIT', label: 'Not stable visit' },
];
const STATUS_OPTIONS = [
  { value: 'ACTIVE', label: 'Active' },
  { value: 'INACTIVE', label: 'Inactive' },
];
const PUBLICATION_OPTIONS = [
  { value: 'UNPUBLISHED', label: 'Unpublished' },
  { value: 'PUBLISHED', label: 'Published' },
];

interface DoctorFormProps {
  initialData?: DoctorResponse;
  onSuccess: (doctor: DoctorResponse) => void;
  onCancel: () => void;
}

export function DoctorForm({ initialData, onSuccess, onCancel }: DoctorFormProps) {
  const isEdit = Boolean(initialData);

  // ── Core fields ──────────────────────────────────────────────────────────────
  const [name, setName] = useState(initialData?.name ?? '');
  const [professionalTitle, setProfessionalTitle] = useState(initialData?.professional_title ?? '');
  const [website, setWebsite] = useState(initialData?.website ?? '');
  const [visitStability, setVisitStability] = useState(initialData?.visit_stability ?? '');
  const [biography, setBiography] = useState(initialData?.biography ?? '');
  const [yearsExperience, setYearsExperience] = useState(
    initialData?.years_experience != null ? String(initialData.years_experience) : ''
  );
  const [experienceDescription, setExperienceDescription] = useState(
    initialData?.experience_description ?? ''
  );
  const [status, setStatus] = useState<ProviderStatus>(initialData?.status ?? 'ACTIVE');
  const [publication, setPublication] = useState<PublicationStatus>(
    initialData?.publication_status ?? 'UNPUBLISHED'
  );

  // ── Contact ──────────────────────────────────────────────────────────────────
  const [phoneEntries, setPhoneEntries] = useState<PhoneEntry[]>(() =>
    initialData?.phones.map((p) => ({
      id: p.id,
      country_code: p.country_code,
      number: p.number,
      is_primary: p.is_primary,
    })) ?? []
  );
  const [emailEntries, setEmailEntries] = useState<EmailEntry[]>(() =>
    initialData?.emails.map((e) => ({
      id: e.id,
      email: e.email,
      is_primary: e.is_primary,
    })) ?? []
  );
  const [phoneErrors, setPhoneErrors] = useState<Record<number, string>>({});
  const [emailErrors, setEmailErrors] = useState<Record<number, string>>({});

  // ── Specializations ──────────────────────────────────────────────────────────
  const [specializations, setSpecializations] = useState<Specialization[]>([]);
  const [specsError, setSpecsError] = useState<string | null>(null);
  const [specFilter, setSpecFilter] = useState('');
  const [selectedSpecIds, setSelectedSpecIds] = useState<string[]>(
    initialData?.specializations.map((s) => s.id) ?? []
  );

  // ── Form state ───────────────────────────────────────────────────────────────
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [apiError, setApiError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Load all active specializations
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const all: Specialization[] = [];
        let page = 1;
        for (;;) {
          const res = await listSpecializations({ is_active: true, page, page_size: 100 });
          all.push(...res.data);
          if (page >= res.meta.total_pages) break;
          page += 1;
        }
        if (!cancelled) setSpecializations(all);
      } catch (err) {
        if (!cancelled) setSpecsError(extractErrorMessage(err, 'Failed to load specializations.'));
      }
    })();
    return () => { cancelled = true; };
  }, []);

  function toggleSpec(id: string) {
    setSelectedSpecIds((ids) =>
      ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id]
    );
  }

  function validate(): boolean {
    const errors: Record<string, string> = {};
    if (!name.trim()) errors.name = 'Name is required.';
    if (!visitStability) errors.visit_stability = 'Visit stability is required.';
    const phErrors: Record<number, string> = {};
    phoneEntries.forEach((p, i) => {
      if (!p.number.trim()) phErrors[i] = 'Enter a number or remove this row.';
    });
    const emErrors: Record<number, string> = {};
    emailEntries.forEach((e, i) => {
      if (!e.email.trim()) emErrors[i] = 'Enter an email or remove this row.';
    });
    setPhoneErrors(phErrors);
    setEmailErrors(emErrors);
    setFieldErrors(errors);
    return (
      Object.keys(errors).length === 0 &&
      Object.keys(phErrors).length === 0 &&
      Object.keys(emErrors).length === 0
    );
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setApiError(null);
    if (!validate()) return;

    setSubmitting(true);
    try {
      let saved: DoctorResponse;

      if (isEdit && initialData) {
        // ── Core fields PATCH ──────────────────────────────────────────────────
        const body: DoctorUpdate = {
          name: name.trim(),
          visit_stability: visitStability as VisitStability,
          website: website.trim() || null,
          professional_title: professionalTitle.trim() || null,
          biography: biography.trim() || null,
          years_experience: yearsExperience ? Number(yearsExperience) : null,
          experience_description: experienceDescription.trim() || null,
        };
        saved = await updateDoctor(initialData.id, body);

        // Status / publication via dedicated endpoints when changed
        if (status !== initialData.status) {
          saved = await updateDoctorStatus(initialData.id, status);
        }
        if (publication !== initialData.publication_status) {
          saved = await updateDoctorPublication(
            initialData.id,
            publication
          );
        }

        // ── Specialization diff ────────────────────────────────────────────────
        const originalSpecIds = initialData.specializations.map((s) => s.id);
        const specsToAdd = selectedSpecIds.filter((id) => !originalSpecIds.includes(id));
        const specsToRemove = originalSpecIds.filter((id) => !selectedSpecIds.includes(id));
        for (const specId of specsToAdd) {
          saved = await addDoctorSpecialization(initialData.id, specId);
        }
        for (const specId of specsToRemove) {
          saved = await removeDoctorSpecialization(initialData.id, specId);
        }

        // ── Phone diff ─────────────────────────────────────────────────────────
        const keptPhoneIds = new Set<string>();
        const phonesToAdd: PhoneEntry[] = [];
        for (const entry of phoneEntries) {
          const orig = entry.id ? initialData.phones.find((p) => p.id === entry.id) : undefined;
          const unchanged =
            orig &&
            orig.country_code === entry.country_code &&
            orig.number === entry.number.trim() &&
            orig.is_primary === entry.is_primary;
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

        // ── Email diff ─────────────────────────────────────────────────────────
        const keptEmailIds = new Set<string>();
        const emailsToAdd: EmailEntry[] = [];
        for (const entry of emailEntries) {
          const orig = entry.id ? initialData.emails.find((em) => em.id === entry.id) : undefined;
          const unchanged =
            orig &&
            orig.email === entry.email.trim() &&
            orig.is_primary === entry.is_primary;
          if (unchanged && entry.id) {
            keptEmailIds.add(entry.id);
          } else {
            emailsToAdd.push(entry);
          }
        }
        const emailsToRemove = initialData.emails.filter((em) => !keptEmailIds.has(em.id));
        for (const em of emailsToRemove) {
          await removeProviderEmail(initialData.id, em.id);
        }
        for (const entry of emailsToAdd) {
          await addProviderEmail(initialData.id, {
            email: entry.email.trim(),
            is_primary: entry.is_primary,
          });
        }

        // Re-fetch if any secondary calls ran
        if (
          specsToAdd.length || specsToRemove.length ||
          phonesToAdd.length || phonesToRemove.length ||
          emailsToAdd.length || emailsToRemove.length ||
          status !== initialData.status ||
          publication !== initialData.publication_status
        ) {
          saved = await getDoctor(initialData.id);
        }
      } else {
        // ── Create ─────────────────────────────────────────────────────────────
        const body: DoctorCreate = {
          name: name.trim(),
          visit_stability: visitStability as VisitStability,
          website: website.trim() || null,
          professional_title: professionalTitle.trim() || null,
          biography: biography.trim() || null,
          years_experience: yearsExperience ? Number(yearsExperience) : null,
          experience_description: experienceDescription.trim() || null,
          status,
          publication_status: publication,
          specialization_ids: selectedSpecIds,
          phones: phoneEntries.map((p) => ({
            country_code: p.country_code,
            number: p.number.trim(),
            is_primary: p.is_primary,
          })),
          emails: emailEntries.map((e) => ({
            email: e.email.trim(),
            is_primary: e.is_primary,
          })),
        };
        saved = await createDoctor(body);
      }

      onSuccess(saved);
    } catch (err) {
      setApiError(extractErrorMessage(err, 'Failed to save doctor. Please try again.'));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} noValidate className={styles.form}>
      {apiError && (
        <div className={`${styles.apiError} ${styles.cardFull}`} role="alert">{apiError}</div>
      )}

      {/* ── Basic information ──────────────────────────────────────────────── */}
      <Card padding="lg" shadow="sm">
        <section className={styles.section}>
          <h3 className={styles.sectionTitle}>Basic information</h3>
          <div className={styles.grid}>
            <Input
              label="Full name"
              placeholder="e.g. Dr. Priya Sharma"
              value={name}
              onChange={(e) => setName(e.target.value)}
              error={fieldErrors.name}
              required
              maxLength={300}
            />
            <Input
              label="Professional title"
              placeholder="e.g. Senior Cardiologist"
              value={professionalTitle}
              onChange={(e) => setProfessionalTitle(e.target.value)}
              maxLength={200}
            />
          </div>
          <Input
            label="Website"
            type="url"
            placeholder="https://example.com"
            value={website}
            onChange={(e) => setWebsite(e.target.value)}
          />
        </section>
      </Card>

      {/* ── Professional info ──────────────────────────────────────────────── */}
      <Card padding="lg" shadow="sm">
        <section className={styles.section}>
          <h3 className={styles.sectionTitle}>Professional info</h3>
          <Input
            label="Years of experience"
            type="number"
            placeholder="e.g. 12"
            value={yearsExperience}
            onChange={(e) => setYearsExperience(e.target.value)}
            min={0}
            max={80}
          />
          <FormField label="Biography" optional htmlFor="doctor-bio">
            <textarea
              id="doctor-bio"
              className={styles.textarea}
              placeholder="Brief biography of this doctor…"
              rows={4}
              value={biography}
              onChange={(e) => setBiography(e.target.value)}
            />
          </FormField>
          <FormField label="Experience notes" optional htmlFor="doctor-exp-desc">
            <textarea
              id="doctor-exp-desc"
              className={styles.textarea}
              placeholder="Detailed experience description…"
              rows={3}
              value={experienceDescription}
              onChange={(e) => setExperienceDescription(e.target.value)}
            />
          </FormField>
        </section>
      </Card>

      {/* ── Contact ────────────────────────────────────────────────────────── */}
      <Card padding="lg" shadow="sm">
        <section className={styles.section}>
          <h3 className={styles.sectionTitle}>
            Contact <span className={styles.optionalTag}>— optional</span>
          </h3>
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
      </Card>

      {/* ── Classification ─────────────────────────────────────────────────── */}
      <Card padding="lg" shadow="sm">
        <section className={styles.section}>
          <h3 className={styles.sectionTitle}>Classification</h3>
          <div className={styles.grid}>
            <Select
              label="Visit stability"
              options={VISIT_STABILITY_OPTIONS}
              placeholder="Select…"
              value={visitStability}
              onChange={(e) => setVisitStability(e.target.value)}
              error={fieldErrors.visit_stability}
              required
            />
            <Select
              label="Status"
              options={STATUS_OPTIONS}
              value={status}
              onChange={(e) => setStatus(e.target.value as ProviderStatus)}
            />
            <Select
              label="Publication status"
              options={PUBLICATION_OPTIONS}
              value={publication}
              onChange={(e) => setPublication(e.target.value as PublicationStatus)}
            />
          </div>
        </section>
      </Card>

      {/* ── Specializations ────────────────────────────────────────────────── */}
      <Card padding="lg" shadow="sm" className={styles.cardFull}>
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
              .filter((spec) => spec.name.toLowerCase().includes(specFilter.toLowerCase()))
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
      </Card>

      <footer className={`${styles.footer} ${styles.cardFull}`}>
        <Button type="button" variant="ghost" onClick={onCancel} disabled={submitting}>
          Cancel
        </Button>
        <Button type="submit" variant="primary" loading={submitting}>
          {isEdit ? 'Save changes' : 'Create doctor'}
        </Button>
      </footer>
    </form>
  );
}
