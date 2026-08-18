/**
 * ProviderForm — shared create / edit form for providers.
 *
 * Props:
 *   initialData — pre-populate fields when editing (undefined = create mode)
 *   onSuccess(provider) — called with the saved provider on success
 *   onCancel() — called when the user dismisses the form
 */
import { useEffect, useState } from 'react';
import { extractErrorMessage } from '@/api/client';
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
  Provider,
  ProviderCreate,
  ProviderLocationCreate,
  ProviderStatus,
  ProviderType,
  PublicationStatus,
  Specialization,
  VisitStability,
} from '@/types';
import styles from './ProviderForm.module.css';

const PROVIDER_TYPE_OPTIONS = [
  { value: 'HOSPITAL', label: 'Hospital' },
  { value: 'CLINIC', label: 'Clinic' },
  { value: 'DOCTOR', label: 'Doctor' },
];
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

interface LocationValues {
  address_line_1: string;
  address_line_2: string;
  city: string;
  state_province: string;
  country: string;
  postal_code: string;
}

const EMPTY_LOCATION: LocationValues = {
  address_line_1: '',
  address_line_2: '',
  city: '',
  state_province: '',
  country: '',
  postal_code: '',
};

interface ProviderFormProps {
  initialData?: Provider;
  onSuccess: (provider: Provider) => void;
  onCancel: () => void;
}

export function ProviderForm({ initialData, onSuccess, onCancel }: ProviderFormProps) {
  const isEdit = Boolean(initialData);

  const [providerType, setProviderType] = useState<string>(initialData?.provider_type ?? '');
  const [name, setName] = useState(initialData?.name ?? '');
  const [description, setDescription] = useState(initialData?.description ?? '');
  const [website, setWebsite] = useState(initialData?.website ?? '');
  const [phoneEntries, setPhoneEntries] = useState<PhoneEntry[]>(() => {
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
  const [visitStability, setVisitStability] = useState<string>(initialData?.visit_stability ?? '');
  const [status, setStatus] = useState<string>(initialData?.status ?? 'ACTIVE');
  const [publication, setPublication] = useState<string>(
    initialData?.publication_status ?? 'UNPUBLISHED'
  );
  const [selectedSpecIds, setSelectedSpecIds] = useState<string[]>(
    initialData?.specializations.map((s) => s.id) ?? []
  );

  // Location — pre-populate from the existing primary location in edit mode.
  const [location, setLocation] = useState<LocationValues>(() => {
    if (!initialData) return EMPTY_LOCATION;
    const primary =
      initialData.locations.find((l) => l.is_primary) ?? initialData.locations[0];
    if (!primary) return EMPTY_LOCATION;
    return {
      address_line_1: primary.address_line_1,
      address_line_2: primary.address_line_2 ?? '',
      city: primary.city,
      state_province: primary.state_province ?? '',
      country: primary.country ?? '',
      postal_code: primary.postal_code ?? '',
    };
  });

  const [specializations, setSpecializations] = useState<Specialization[]>([]);
  const [specsError, setSpecsError] = useState<string | null>(null);
  const [specFilter, setSpecFilter] = useState('');

  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [apiError, setApiError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Load active specializations for the multi-select (page through all).
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const all: Specialization[] = [];
        let pageNum = 1;
        for (;;) {
          const res = await listSpecializations({ is_active: true, page: pageNum, page_size: 100 });
          all.push(...res.data);
          if (pageNum >= res.meta.total_pages) break;
          pageNum += 1;
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
    if (!providerType) errors.provider_type = 'Provider type is required.';
    if (!name.trim()) errors.name = 'Name is required.';
    if (!visitStability) errors.visit_stability = 'Visit stability is required.';
    if (location.address_line_1.trim() && !location.city.trim()) {
      errors.city = 'City is required when an address is provided.';
    }
    if (location.city.trim() && !location.address_line_1.trim()) {
      errors.address_line_1 = 'Address line 1 is required when a city is provided.';
    }
    // Contact rows are optional, but existing rows must be non-empty.
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
      let saved: Provider;
      if (isEdit && initialData) {
        saved = await updateProvider(initialData.id, {
          provider_type: providerType as ProviderType,
          name: name.trim(),
          description: description.trim() || null,
          website: website.trim() || null,
          visit_stability: visitStability as VisitStability,
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
        if (locationFilled) {
          const primaryLoc =
            initialData.locations.find((l) => l.is_primary) ??
            initialData.locations[0];
          const locBody = {
            address_line_1: location.address_line_1.trim(),
            address_line_2: location.address_line_2.trim() || null,
            city: location.city.trim(),
            state_province: location.state_province.trim() || null,
            country: location.country.trim() || null,
            postal_code: location.postal_code.trim() || null,
            is_primary: true,
          };
          if (primaryLoc) {
            await updateProviderLocation(initialData.id, primaryLoc.id, locBody);
          } else {
            await createProviderLocation(initialData.id, locBody);
          }
        }

        if (
          toAdd.length || toRemove.length ||
          phonesToAdd.length || phonesToRemove.length ||
          emailsToAdd.length || emailsToRemove.length ||
          status !== initialData.status ||
          publication !== initialData.publication_status ||
          locationFilled
        ) {
          saved = await getProvider(initialData.id);
        }
      } else {
        let primary_location: ProviderLocationCreate | null = null;
        if (location.address_line_1.trim() && location.city.trim()) {
          primary_location = {
            address_line_1: location.address_line_1.trim(),
            address_line_2: location.address_line_2.trim() || null,
            city: location.city.trim(),
            state_province: location.state_province.trim() || null,
            country: location.country.trim() || null,
            postal_code: location.postal_code.trim() || null,
            is_primary: true,
          };
        }
        const body: ProviderCreate = {
          provider_type: providerType as ProviderType,
          name: name.trim(),
          visit_stability: visitStability as VisitStability,
          description: description.trim() || null,
          website: website.trim() || null,
          status: status as ProviderStatus,
          publication_status: publication as PublicationStatus,
          specialization_ids: selectedSpecIds,
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
        };
        saved = await createProvider(body);
      }
      onSuccess(saved);
    } catch (err) {
      setApiError(extractErrorMessage(err, 'Failed to save provider. Please try again.'));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} noValidate className={styles.form}>
      {apiError && (
        <div className={styles.apiError} role="alert">{apiError}</div>
      )}

      {/* ── Basic information ─────────────────────────────────────────────── */}
      <Card padding="lg" shadow="sm">
        <section className={styles.section}>
          <h3 className={styles.sectionTitle}>Basic information</h3>
          <div className={styles.grid}>
            <Select
              label="Provider type"
              options={PROVIDER_TYPE_OPTIONS}
              placeholder="Select type…"
              value={providerType}
              onChange={(e) => setProviderType(e.target.value)}
              error={fieldErrors.provider_type}
              required
            />
            <Input
              label="Name"
              placeholder="e.g. St. Mary's Hospital"
              value={name}
              onChange={(e) => setName(e.target.value)}
              error={fieldErrors.name}
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
        </section>
      </Card>

      {/* ── Contact ───────────────────────────────────────────────────────── */}
      <Card padding="lg" shadow="sm">
        <section className={styles.section}>
          <h3 className={styles.sectionTitle}>Contact <span className={styles.optionalTag}>— optional</span></h3>
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

      {/* ── Specializations ───────────────────────────────────────────────── */}
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
      </Card>

      {/* ── Classification ────────────────────────────────────────────────── */}
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
              onChange={(e) => setStatus(e.target.value)}
            />
            <Select
              label="Publication status"
              options={PUBLICATION_OPTIONS}
              value={publication}
              onChange={(e) => setPublication(e.target.value)}
            />
          </div>
        </section>
      </Card>

      {/* ── Primary location — shown in both Add and Edit ─────────────────── */}
      <Card padding="lg" shadow="sm">
        <section className={styles.section}>
          <h3 className={styles.sectionTitle}>
            Primary location <span className={styles.optionalTag}>— optional</span>
          </h3>
          <div className={styles.grid}>
            <Input
              label="Address line 1"
              value={location.address_line_1}
              onChange={(e) => setLocation((l) => ({ ...l, address_line_1: e.target.value }))}
              error={fieldErrors.address_line_1}
            />
            <Input
              label="Address line 2"
              value={location.address_line_2}
              onChange={(e) => setLocation((l) => ({ ...l, address_line_2: e.target.value }))}
            />
            <Input
              label="City"
              value={location.city}
              onChange={(e) => setLocation((l) => ({ ...l, city: e.target.value }))}
              error={fieldErrors.city}
            />
            <Input
              label="State / Province"
              value={location.state_province}
              onChange={(e) => setLocation((l) => ({ ...l, state_province: e.target.value }))}
            />
            <Input
              label="Country"
              value={location.country}
              onChange={(e) => setLocation((l) => ({ ...l, country: e.target.value }))}
            />
            <Input
              label="Postal code"
              value={location.postal_code}
              onChange={(e) => setLocation((l) => ({ ...l, postal_code: e.target.value }))}
            />
          </div>
        </section>
      </Card>

      <footer className={`${styles.footer} ${styles.cardFull}`}>
        <Button type="button" variant="ghost" onClick={onCancel} disabled={submitting}>
          Cancel
        </Button>
        <Button type="submit" variant="primary" loading={submitting}>
          {isEdit ? 'Save changes' : 'Create provider'}
        </Button>
      </footer>
    </form>
  );
}
