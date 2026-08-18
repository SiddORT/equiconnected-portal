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
  addProviderSpecialization,
  createProvider,
  getProvider,
  removeProviderSpecialization,
  updateProvider,
  updateProviderPublication,
  updateProviderStatus,
} from '@/api/providers';
import { listSpecializations } from '@/api/specializations';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { FormField } from '@/components/ui/FormField';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
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
  const [email, setEmail] = useState(initialData?.email ?? '');
  const [phone, setPhone] = useState(initialData?.phone ?? '');
  const [website, setWebsite] = useState(initialData?.website ?? '');
  const [visitStability, setVisitStability] = useState<string>(initialData?.visit_stability ?? '');
  const [status, setStatus] = useState<string>(initialData?.status ?? 'ACTIVE');
  const [publication, setPublication] = useState<string>(
    initialData?.publication_status ?? 'UNPUBLISHED'
  );
  const [selectedSpecIds, setSelectedSpecIds] = useState<string[]>(
    initialData?.specializations.map((s) => s.id) ?? []
  );
  const [location, setLocation] = useState<LocationValues>(EMPTY_LOCATION);

  const [specializations, setSpecializations] = useState<Specialization[]>([]);
  const [specsError, setSpecsError] = useState<string | null>(null);

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
    if (!isEdit && location.address_line_1.trim() && !location.city.trim()) {
      errors.city = 'City is required when an address is provided.';
    }
    if (!isEdit && location.city.trim() && !location.address_line_1.trim()) {
      errors.address_line_1 = 'Address line 1 is required when a city is provided.';
    }
    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
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
          email: email.trim() || null,
          phone: phone.trim() || null,
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
        if (toAdd.length || toRemove.length || status !== initialData.status || publication !== initialData.publication_status) {
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
          email: email.trim() || null,
          phone: phone.trim() || null,
          website: website.trim() || null,
          status: status as ProviderStatus,
          publication_status: publication as PublicationStatus,
          specialization_ids: selectedSpecIds,
          primary_location,
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

          <div className={styles.grid}>
            <Input
              label="Email"
              type="email"
              placeholder="contact@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            <Input
              label="Phone"
              type="tel"
              placeholder="+1 555 000 0000"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
            />
            <Input
              label="Website"
              type="url"
              placeholder="https://example.com"
              value={website}
              onChange={(e) => setWebsite(e.target.value)}
            />
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

      {/* ── Specializations ───────────────────────────────────────────────── */}
      <Card padding="lg" shadow="sm">
        <section className={styles.section}>
          <h3 className={styles.sectionTitle}>Specializations</h3>
          {specsError && <p className={styles.fieldError} role="alert">{specsError}</p>}
          {!specsError && specializations.length === 0 && (
            <p className={styles.hint}>No active specializations available.</p>
          )}
          <div className={styles.specGrid}>
            {specializations.map((spec) => (
              <label key={spec.id} className={styles.checkboxRow}>
                <input
                  type="checkbox"
                  checked={selectedSpecIds.includes(spec.id)}
                  onChange={() => toggleSpec(spec.id)}
                />
                <span>{spec.name}</span>
              </label>
            ))}
          </div>
        </section>
      </Card>

      {/* ── Primary location (create mode only) ───────────────────────────── */}
      {!isEdit && (
        <Card padding="lg" shadow="sm">
          <section className={styles.section}>
            <h3 className={styles.sectionTitle}>Primary location <span className={styles.optionalTag}>— optional</span></h3>
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
      )}

      <footer className={styles.footer}>
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
