/**
 * Provider Detail page — /admin/providers/:id
 * Compact layout: Overview+Info (full) | Specializations+Locations (split) | Photos (full)
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { extractErrorMessage } from '@/api/client';
import {
  addProviderSpecialization,
  createProviderLocation,
  deleteProviderLocation,
  deleteProviderPhoto,
  getProvider,
  removeProviderSpecialization,
  setProviderThumbnail,
  updateProviderLocation,
  updateProviderPublication,
  updateProviderStatus,
  uploadProviderPhoto,
} from '@/api/providers';
import { listSpecializations } from '@/api/specializations';
import { DoctorProfessionalSections } from '@/components/admin/DoctorProfessionalSections';
import { ActionMenu } from '@/components/ui/ActionMenu';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { Input } from '@/components/ui/Input';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { Select } from '@/components/ui/Select';
import { PageHeader } from '@/components/layout/PageHeader';
import type { LoadingState, Provider, Specialization } from '@/types';
import styles from './ProviderDetailPage.module.css';

const TYPE_LABELS: Record<string, string> = {
  HOSPITAL: 'Hospital',
  CLINIC: 'Clinic',
  DOCTOR: 'Doctor',
};

interface LocationFormValues {
  name: string;
  address_line_1: string;
  address_line_2: string;
  city: string;
  state_province: string;
  country: string;
  postal_code: string;
  latitude: string;
  longitude: string;
  is_primary: boolean;
}

const EMPTY_LOCATION_FORM: LocationFormValues = {
  name: '',
  address_line_1: '',
  address_line_2: '',
  city: '',
  state_province: '',
  country: '',
  postal_code: '',
  latitude: '',
  longitude: '',
  is_primary: false,
};

interface StagedPhoto {
  id: string;
  file: File;
  preview: string;
  status: 'pending' | 'uploading' | 'done' | 'error';
  alt_text: string;
  caption: string;
}

function isImageUrl(ref: string) {
  return (
    ref.startsWith('data:image') ||
    ref.startsWith('/uploads/') ||
    /\.(png|jpe?g|gif|webp|svg)(\?|$)/i.test(ref)
  );
}

export function ProviderDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [provider, setProvider] = useState<Provider | null>(null);
  const [loadState, setLoadState] = useState<LoadingState>('loading');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Add-specialization select
  const [allSpecs, setAllSpecs] = useState<Specialization[]>([]);
  const [specToAdd, setSpecToAdd] = useState('');

  // Add-location form
  const [locationFormOpen, setLocationFormOpen] = useState(false);
  const [locationForm, setLocationForm] = useState<LocationFormValues>(EMPTY_LOCATION_FORM);

  // Edit-location form
  const [editingLocationId, setEditingLocationId] = useState<string | null>(null);
  const [editLocationForm, setEditLocationForm] = useState<LocationFormValues>(EMPTY_LOCATION_FORM);

  function openEditLocation(loc: import('@/types').ProviderLocation) {
    setEditingLocationId(loc.id);
    setEditLocationForm({
      name: loc.name ?? '',
      address_line_1: loc.address_line_1,
      address_line_2: loc.address_line_2 ?? '',
      city: loc.city,
      state_province: loc.state_province ?? '',
      country: loc.country ?? '',
      postal_code: loc.postal_code ?? '',
      latitude: loc.latitude != null ? String(loc.latitude) : '',
      longitude: loc.longitude != null ? String(loc.longitude) : '',
      is_primary: loc.is_primary,
    });
  }

  function closeEditLocation() {
    setEditingLocationId(null);
    setEditLocationForm(EMPTY_LOCATION_FORM);
  }

  // Confirm dialog
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [confirmProps, setConfirmProps] = useState<{
    title: string;
    message?: string;
    danger?: boolean;
    onConfirm: () => void;
  }>({ title: '', onConfirm: () => {} });

  function openConfirm(title: string, message: string, onConfirm: () => void, danger = true) {
    setConfirmProps({ title, message, danger, onConfirm });
    setConfirmOpen(true);
  }

  // Add-photo form
  const [photoFormOpen, setPhotoFormOpen] = useState(false);
  const [stagedPhotos, setStagedPhotos] = useState<StagedPhoto[]>([]);
  const [uploading, setUploading] = useState(false);
  const [isDragOver, setIsDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    if (!id) return;
    setLoadState('loading');
    try {
      setProvider(await getProvider(id));
      setLoadState('success');
    } catch (err) {
      setErrorMessage(extractErrorMessage(err, 'Failed to load provider.'));
      setLoadState('error');
    }
  }, [id]);

  useEffect(() => { void load(); }, [load]);

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
        if (!cancelled) setAllSpecs(all);
      } catch {
        /* non-fatal */
      }
    })();
    return () => { cancelled = true; };
  }, []);

  async function run(action: () => Promise<unknown>, failMessage: string) {
    setBusy(true);
    setActionError(null);
    try {
      await action();
      await load();
    } catch (err) {
      setActionError(extractErrorMessage(err, failMessage));
    } finally {
      setBusy(false);
    }
  }

  function addFiles(files: FileList | File[]) {
    const arr = Array.from(files).filter((f) => f.type.startsWith('image/'));
    arr.forEach((file) => {
      const id = `${Date.now()}-${Math.random()}`;
      const reader = new FileReader();
      reader.onload = (ev) => {
        setStagedPhotos((prev) => [
          ...prev,
          { id, file, preview: ev.target?.result as string, status: 'pending', alt_text: '', caption: '' },
        ]);
      };
      reader.readAsDataURL(file);
    });
    if (fileInputRef.current) fileInputRef.current.value = '';
  }

  function updateStagedMeta(id: string, patch: { alt_text?: string; caption?: string }) {
    setStagedPhotos((prev) => prev.map((sp) => sp.id === id ? { ...sp, ...patch } : sp));
  }

  function removeStagedPhoto(id: string) {
    setStagedPhotos((prev) => prev.filter((p) => p.id !== id));
  }

  function resetPhotoForm() {
    setStagedPhotos([]);
    setUploading(false);
    if (fileInputRef.current) fileInputRef.current.value = '';
  }

  async function handleUploadAll() {
    if (stagedPhotos.length === 0) return;
    setUploading(true);
    setActionError(null);

    const results = await Promise.allSettled(
      stagedPhotos.map((sp) =>
        uploadProviderPhoto(p!.id, sp.file, {
          alt_text: sp.alt_text.trim() || null,
          caption: sp.caption.trim() || null,
        }).then(() => {
          setStagedPhotos((prev) =>
            prev.map((x) => (x.id === sp.id ? { ...x, status: 'done' } : x))
          );
        }).catch(() => {
          setStagedPhotos((prev) =>
            prev.map((x) => (x.id === sp.id ? { ...x, status: 'error' } : x))
          );
          throw sp.file.name;
        })
      )
    );

    const failed = results.filter((r) => r.status === 'rejected').map((r) => (r as PromiseRejectedResult).reason);
    await load();

    if (failed.length === 0) {
      resetPhotoForm();
      setPhotoFormOpen(false);
    } else {
      setActionError(`Failed to upload: ${failed.join(', ')}`);
      setStagedPhotos((prev) => prev.filter((x) => x.status !== 'done'));
      setUploading(false);
    }
  }

  if (loadState === 'loading') {
    return (
      <div className={styles.centeredPage}>
        <LoadingSpinner size="lg" label="Loading provider…" />
      </div>
    );
  }

  if (loadState === 'error' || !provider) {
    return (
      <div className={styles.centeredPage}>
        <ErrorState title="Failed to load provider" message={errorMessage ?? undefined} onRetry={load} />
      </div>
    );
  }

  const p = provider;
  const availableSpecs = allSpecs.filter(
    (s) => !p.specializations.some((assigned) => assigned.id === s.id)
  );

  const primaryEmail =
    p.emails.length > 0
      ? (p.emails.find((e) => e.is_primary) ?? p.emails[0]).email
      : (p.email ?? null);

  const primaryPhone =
    p.phones.length > 0
      ? (() => {
          const ph = p.phones.find((x) => x.is_primary) ?? p.phones[0];
          return `${ph.country_code} ${ph.number}`;
        })()
      : (p.phone ?? null);

  return (
    <div className={styles.shell}>
      <PageHeader
        title={p.name}
        subtitle={`${TYPE_LABELS[p.provider_type] ?? p.provider_type} profile`}
        breadcrumbs={[
          { label: 'Admin' },
          { label: 'Providers', href: '/admin/providers' },
          { label: p.name },
        ]}
        actions={
          <>
            <Button variant="outline" onClick={() => navigate(`/admin/providers/${p.id}/edit`)} leftIcon="✏️">
              Edit
            </Button>
            <ActionMenu
              ariaLabel="Provider actions"
              items={[
                {
                  label: p.status === 'ACTIVE' ? 'Deactivate' : 'Activate',
                  icon: p.status === 'ACTIVE' ? '⊘' : '✓',
                  danger: p.status === 'ACTIVE',
                  disabled: busy,
                  onSelect: () =>
                    run(
                      () => updateProviderStatus(p.id, p.status === 'ACTIVE' ? 'INACTIVE' : 'ACTIVE'),
                      'Failed to update status.'
                    ),
                },
                {
                  label: p.publication_status === 'PUBLISHED' ? 'Unpublish' : 'Publish',
                  icon: p.publication_status === 'PUBLISHED' ? '📕' : '📗',
                  disabled: busy,
                  onSelect: () =>
                    run(
                      () =>
                        updateProviderPublication(
                          p.id,
                          p.publication_status === 'PUBLISHED' ? 'UNPUBLISHED' : 'PUBLISHED'
                        ),
                      'Failed to update publication status.'
                    ),
                },
              ]}
            />
          </>
        }
      />

      <div className={styles.body}>
        {actionError && (
          <div className={`${styles.actionError} ${styles.colFull}`} role="alert">{actionError}</div>
        )}

        {/* ── Overview + Basic Info — full width ─────────────────────────────── */}
        <Card padding="none" shadow="sm" className={styles.colFull}>
          <div className={styles.overviewCard}>
            <div className={styles.overviewHeader}>
              <h2 className={styles.sectionTitle}>Overview</h2>
              <div className={styles.badgeRow}>
                <Badge variant="info">{TYPE_LABELS[p.provider_type] ?? p.provider_type}</Badge>
                <Badge variant={p.status === 'ACTIVE' ? 'success' : 'neutral'}>
                  {p.status === 'ACTIVE' ? 'Active' : 'Inactive'}
                </Badge>
                <Badge variant={p.publication_status === 'PUBLISHED' ? 'info' : 'neutral'}>
                  {p.publication_status === 'PUBLISHED' ? 'Published' : 'Unpublished'}
                </Badge>
                <Badge variant={p.visit_stability === 'STABLE_VISIT' ? 'success' : 'warning'}>
                  {p.visit_stability === 'STABLE_VISIT' ? 'Stable' : 'Not stable'}
                </Badge>
              </div>
            </div>
            <dl className={styles.infoStrip}>
              <div>
                <dt>Email</dt>
                <dd>{primaryEmail ?? '—'}</dd>
              </div>
              <div>
                <dt>Phone</dt>
                <dd>{primaryPhone ?? '—'}</dd>
              </div>
              <div>
                <dt>Website</dt>
                <dd>
                  {p.website
                    ? <a href={p.website} target="_blank" rel="noreferrer">{p.website}</a>
                    : '—'}
                </dd>
              </div>
              <div>
                <dt>Created</dt>
                <dd>{new Date(p.created_at).toLocaleString()}</dd>
              </div>
              <div>
                <dt>Updated</dt>
                <dd>{new Date(p.updated_at).toLocaleString()}</dd>
              </div>
            </dl>
            {p.description && <p className={styles.overviewDescription}>{p.description}</p>}
          </div>
        </Card>

        {/* ── Professional info — doctors only ─────────────────────────────── */}
        {p.provider_type === 'DOCTOR' && (
          <Card padding="none" shadow="sm" className={styles.colFull}>
            <CardHeader><h2 className={styles.sectionTitle}>Professional info</h2></CardHeader>
            <CardBody>
              {p.doctor_profile &&
              (p.doctor_profile.professional_title ||
                p.doctor_profile.biography ||
                p.doctor_profile.years_experience != null ||
                p.doctor_profile.experience_description) ? (
                <dl className={styles.infoStrip}>
                  <div>
                    <dt>Professional title</dt>
                    <dd>{p.doctor_profile.professional_title ?? '—'}</dd>
                  </div>
                  <div>
                    <dt>Years of experience</dt>
                    <dd>{p.doctor_profile.years_experience ?? '—'}</dd>
                  </div>
                  <div>
                    <dt>Biography</dt>
                    <dd>{p.doctor_profile.biography ?? '—'}</dd>
                  </div>
                  <div>
                    <dt>Experience notes</dt>
                    <dd>{p.doctor_profile.experience_description ?? '—'}</dd>
                  </div>
                </dl>
              ) : (
                <EmptyState
                  icon="👨‍⚕️"
                  title="No professional info yet"
                  description="Edit this provider to add title, experience, and biography."
                />
              )}
            </CardBody>
          </Card>
        )}

        {/* ── Qualifications & affiliations — doctors only ─────────────────── */}
        {p.provider_type === 'DOCTOR' && <DoctorProfessionalSections providerId={p.id} />}

        {/* ── Specializations — left ────────────────────────────────────────── */}
        <Card padding="none" shadow="sm">
          <CardHeader><h2 className={styles.sectionTitle}>Specializations</h2></CardHeader>
          <CardBody>
            {p.specializations.length === 0 ? (
              <EmptyState icon="⚕" title="No specializations assigned" />
            ) : (
              <ul className={styles.pillList}>
                {p.specializations.map((s) => (
                  <li key={s.id} className={styles.pill}>
                    <span>{s.name}</span>
                    <button
                      type="button"
                      className={styles.pillRemove}
                      aria-label={`Remove ${s.name}`}
                      disabled={busy}
                      onClick={() =>
                        run(() => removeProviderSpecialization(p.id, s.id), 'Failed to remove specialization.')
                      }
                    >
                      ✕
                    </button>
                  </li>
                ))}
              </ul>
            )}
            <div className={styles.addRow}>
              <Select
                aria-label="Add specialization"
                options={availableSpecs.map((s) => ({ value: s.id, label: s.name }))}
                placeholder="Select specialization…"
                value={specToAdd}
                onChange={(e) => setSpecToAdd(e.target.value)}
                containerClassName={styles.addSelect}
              />
              <Button
                variant="outline"
                size="sm"
                disabled={!specToAdd || busy}
                onClick={() =>
                  run(async () => {
                    await addProviderSpecialization(p.id, specToAdd);
                    setSpecToAdd('');
                  }, 'Failed to add specialization.')
                }
              >
                Add
              </Button>
            </div>
          </CardBody>
        </Card>

        {/* ── Locations — right ────────────────────────────────────────────── */}
        <Card padding="none" shadow="sm">
          <CardHeader>
            <div className={styles.cardHeaderRow}>
              <h2 className={styles.sectionTitle}>Locations</h2>
              <Button variant="outline" size="sm" onClick={() => setLocationFormOpen((o) => !o)}>
                {locationFormOpen ? 'Cancel' : '＋ Add location'}
              </Button>
            </div>
          </CardHeader>
          <CardBody>
            {locationFormOpen && (
              <form
                className={styles.inlineForm}
                onSubmit={(e) => {
                  e.preventDefault();
                  if (!locationForm.address_line_1.trim() || !locationForm.city.trim()) {
                    setActionError('Address line 1 and city are required for a location.');
                    return;
                  }
                  void run(async () => {
                    await createProviderLocation(p.id, {
                      name: locationForm.name.trim() || null,
                      address_line_1: locationForm.address_line_1.trim(),
                      address_line_2: locationForm.address_line_2.trim() || null,
                      city: locationForm.city.trim(),
                      state_province: locationForm.state_province.trim() || null,
                      country: locationForm.country.trim() || null,
                      postal_code: locationForm.postal_code.trim() || null,
                      latitude: locationForm.latitude.trim() ? parseFloat(locationForm.latitude) : null,
                      longitude: locationForm.longitude.trim() ? parseFloat(locationForm.longitude) : null,
                      is_primary: locationForm.is_primary,
                    });
                    setLocationForm(EMPTY_LOCATION_FORM);
                    setLocationFormOpen(false);
                  }, 'Failed to add location.');
                }}
              >
                <div className={styles.formGrid}>
                  <Input
                    label="Location name"
                    placeholder="e.g. Main Branch, Ward 3…"
                    value={locationForm.name}
                    onChange={(e) => setLocationForm((f) => ({ ...f, name: e.target.value }))}
                  />
                  <Input
                    label="Address line 1"
                    required
                    value={locationForm.address_line_1}
                    onChange={(e) => setLocationForm((f) => ({ ...f, address_line_1: e.target.value }))}
                  />
                  <Input
                    label="Address line 2"
                    value={locationForm.address_line_2}
                    onChange={(e) => setLocationForm((f) => ({ ...f, address_line_2: e.target.value }))}
                  />
                  <Input
                    label="City"
                    required
                    value={locationForm.city}
                    onChange={(e) => setLocationForm((f) => ({ ...f, city: e.target.value }))}
                  />
                  <Input
                    label="State / Province"
                    value={locationForm.state_province}
                    onChange={(e) => setLocationForm((f) => ({ ...f, state_province: e.target.value }))}
                  />
                  <Input
                    label="Country"
                    value={locationForm.country}
                    onChange={(e) => setLocationForm((f) => ({ ...f, country: e.target.value }))}
                  />
                  <Input
                    label="Postal code"
                    value={locationForm.postal_code}
                    onChange={(e) => setLocationForm((f) => ({ ...f, postal_code: e.target.value }))}
                  />
                  <Input
                    label="Latitude"
                    type="number"
                    placeholder="-90 to 90"
                    value={locationForm.latitude}
                    onChange={(e) => setLocationForm((f) => ({ ...f, latitude: e.target.value }))}
                  />
                  <Input
                    label="Longitude"
                    type="number"
                    placeholder="-180 to 180"
                    value={locationForm.longitude}
                    onChange={(e) => setLocationForm((f) => ({ ...f, longitude: e.target.value }))}
                  />
                </div>
                <label className={styles.checkboxRow}>
                  <input
                    type="checkbox"
                    checked={locationForm.is_primary}
                    onChange={(e) => setLocationForm((f) => ({ ...f, is_primary: e.target.checked }))}
                  />
                  <span>Set as primary location</span>
                </label>
                <div className={styles.inlineFormFooter}>
                  <Button type="submit" variant="primary" size="sm" loading={busy}>
                    Add location
                  </Button>
                </div>
              </form>
            )}

            {p.locations.length === 0 ? (
              <EmptyState icon="📍" title="No locations yet" description="Add the provider's first location." />
            ) : (
              <ul className={styles.itemList}>
                {p.locations.map((loc) => (
                  <li key={loc.id} className={styles.item}>
                    {editingLocationId === loc.id ? (
                      <form
                        className={styles.inlineForm}
                        onSubmit={(e) => {
                          e.preventDefault();
                          if (!editLocationForm.address_line_1.trim() || !editLocationForm.city.trim()) {
                            setActionError('Address line 1 and city are required.');
                            return;
                          }
                          void run(async () => {
                            await updateProviderLocation(p.id, loc.id, {
                              name: editLocationForm.name.trim() || null,
                              address_line_1: editLocationForm.address_line_1.trim(),
                              address_line_2: editLocationForm.address_line_2.trim() || null,
                              city: editLocationForm.city.trim(),
                              state_province: editLocationForm.state_province.trim() || null,
                              country: editLocationForm.country.trim() || null,
                              postal_code: editLocationForm.postal_code.trim() || null,
                              latitude: editLocationForm.latitude.trim() ? parseFloat(editLocationForm.latitude) : null,
                              longitude: editLocationForm.longitude.trim() ? parseFloat(editLocationForm.longitude) : null,
                              is_primary: editLocationForm.is_primary,
                            });
                            closeEditLocation();
                          }, 'Failed to update location.');
                        }}
                      >
                        <div className={styles.formGrid}>
                          <Input
                            label="Location name"
                            placeholder="e.g. Main Branch, Ward 3…"
                            value={editLocationForm.name}
                            onChange={(e) => setEditLocationForm((f) => ({ ...f, name: e.target.value }))}
                          />
                          <Input
                            label="Address line 1"
                            required
                            value={editLocationForm.address_line_1}
                            onChange={(e) => setEditLocationForm((f) => ({ ...f, address_line_1: e.target.value }))}
                          />
                          <Input
                            label="Address line 2"
                            value={editLocationForm.address_line_2}
                            onChange={(e) => setEditLocationForm((f) => ({ ...f, address_line_2: e.target.value }))}
                          />
                          <Input
                            label="City"
                            required
                            value={editLocationForm.city}
                            onChange={(e) => setEditLocationForm((f) => ({ ...f, city: e.target.value }))}
                          />
                          <Input
                            label="State / Province"
                            value={editLocationForm.state_province}
                            onChange={(e) => setEditLocationForm((f) => ({ ...f, state_province: e.target.value }))}
                          />
                          <Input
                            label="Country"
                            value={editLocationForm.country}
                            onChange={(e) => setEditLocationForm((f) => ({ ...f, country: e.target.value }))}
                          />
                          <Input
                            label="Postal code"
                            value={editLocationForm.postal_code}
                            onChange={(e) => setEditLocationForm((f) => ({ ...f, postal_code: e.target.value }))}
                          />
                          <Input
                            label="Latitude"
                            type="number"
                            placeholder="-90 to 90"
                            value={editLocationForm.latitude}
                            onChange={(e) => setEditLocationForm((f) => ({ ...f, latitude: e.target.value }))}
                          />
                          <Input
                            label="Longitude"
                            type="number"
                            placeholder="-180 to 180"
                            value={editLocationForm.longitude}
                            onChange={(e) => setEditLocationForm((f) => ({ ...f, longitude: e.target.value }))}
                          />
                        </div>
                        <label className={styles.checkboxRow}>
                          <input
                            type="checkbox"
                            checked={editLocationForm.is_primary}
                            onChange={(e) => setEditLocationForm((f) => ({ ...f, is_primary: e.target.checked }))}
                          />
                          <span>Set as primary location</span>
                        </label>
                        <div className={styles.inlineFormFooter}>
                          <Button type="submit" variant="primary" size="sm" loading={busy}>
                            Save changes
                          </Button>
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            disabled={busy}
                            onClick={closeEditLocation}
                          >
                            Cancel
                          </Button>
                        </div>
                      </form>
                    ) : (
                      <>
                        <div className={styles.itemMain}>
                          {loc.name && (
                            <span className={styles.itemLabel}>{loc.name}</span>
                          )}
                          <span className={styles.itemTitle}>
                            {loc.address_line_1}
                            {loc.address_line_2 ? `, ${loc.address_line_2}` : ''}
                          </span>
                          <span className={styles.itemSub}>
                            {[loc.city, loc.state_province, loc.country, loc.postal_code]
                              .filter(Boolean)
                              .join(', ')}
                            {(loc.latitude != null && loc.longitude != null) && (
                              <span className={styles.itemCoords}>
                                {' · '}{Number(loc.latitude).toFixed(5)}, {Number(loc.longitude).toFixed(5)}
                              </span>
                            )}
                          </span>
                        </div>
                        <div className={styles.itemActions}>
                          {loc.is_primary && <Badge variant="info" size="sm">Primary</Badge>}
                          <button
                            type="button"
                            className={styles.editBtn}
                            aria-label="Edit location"
                            disabled={busy}
                            onClick={() => openEditLocation(loc)}
                          >
                            ✏ Edit
                          </button>
                          <button
                            type="button"
                            className={styles.removeBtn}
                            aria-label="Remove location"
                            disabled={busy}
                            onClick={() => {
                              openConfirm(
                                'Remove location?',
                                'This location will be permanently removed from the provider.',
                                () => run(() => deleteProviderLocation(p.id, loc.id), 'Failed to remove location.')
                              );
                            }}
                          >
                            🗑 Remove
                          </button>
                        </div>
                      </>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </CardBody>
        </Card>

        {/* ── Photos — full width ───────────────────────────────────────────── */}
        <Card padding="none" shadow="sm" className={styles.colFull}>
          <CardHeader>
            <div className={styles.cardHeaderRow}>
              <h2 className={styles.sectionTitle}>Photos</h2>
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  if (photoFormOpen) resetPhotoForm();
                  setPhotoFormOpen((o) => !o);
                }}
              >
                {photoFormOpen ? 'Cancel' : '＋ Add photos'}
              </Button>
            </div>
          </CardHeader>
          <CardBody>
            {photoFormOpen && (
              <div className={styles.uploadPanel}>
                {/* Hidden file input */}
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  multiple
                  className={styles.fileInput}
                  onChange={(e) => e.target.files && addFiles(e.target.files)}
                />

                {/* Drop zone */}
                <div
                  className={`${styles.dropZone}${isDragOver ? ` ${styles.dropZoneActive}` : ''}`}
                  onClick={() => fileInputRef.current?.click()}
                  onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
                  onDragLeave={() => setIsDragOver(false)}
                  onDrop={(e) => {
                    e.preventDefault();
                    setIsDragOver(false);
                    addFiles(e.dataTransfer.files);
                  }}
                >
                  <span className={styles.dropZoneIcon}>🖼</span>
                  <span className={styles.dropZoneText}>
                    Drop images here or <span className={styles.dropZoneBrowse}>browse</span>
                  </span>
                  <span className={styles.dropZoneHint}>PNG, JPG, WebP, GIF — multiple allowed</span>
                </div>

                {/* Staged photo cards */}
                {stagedPhotos.length > 0 && (
                  <div className={styles.stagedList}>
                    {stagedPhotos.map((sp) => (
                      <div key={sp.id} className={styles.stagedCard}>
                        {/* Thumbnail */}
                        <div className={styles.stagedThumbWrap}>
                          <img src={sp.preview} alt={sp.file.name} className={styles.stagedThumbImg} />
                          {sp.status === 'uploading' && (
                            <div className={styles.thumbOverlay}>
                              <span className={styles.thumbSpinner} />
                            </div>
                          )}
                          {sp.status === 'done' && (
                            <div className={`${styles.thumbOverlay} ${styles.thumbDone}`}>✓</div>
                          )}
                          {sp.status === 'error' && (
                            <div className={`${styles.thumbOverlay} ${styles.thumbError}`}>!</div>
                          )}
                          {sp.status === 'pending' && (
                            <button
                              type="button"
                              className={styles.thumbRemove}
                              onClick={() => removeStagedPhoto(sp.id)}
                              aria-label={`Remove ${sp.file.name}`}
                            >
                              ✕
                            </button>
                          )}
                        </div>

                        {/* Metadata fields */}
                        <div className={styles.stagedMeta}>
                          <span className={styles.stagedFileName}>{sp.file.name}</span>
                          <label className={styles.stagedLabel}>
                            Alt text
                            <input
                              type="text"
                              className={styles.stagedInput}
                              placeholder="Describe the image for accessibility…"
                              value={sp.alt_text}
                              disabled={sp.status !== 'pending'}
                              onChange={(e) => updateStagedMeta(sp.id, { alt_text: e.target.value })}
                            />
                          </label>
                          <label className={styles.stagedLabel}>
                            Caption
                            <input
                              type="text"
                              className={styles.stagedInput}
                              placeholder="Optional caption…"
                              value={sp.caption}
                              disabled={sp.status !== 'pending'}
                              onChange={(e) => updateStagedMeta(sp.id, { caption: e.target.value })}
                            />
                          </label>
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* Footer */}
                <div className={styles.inlineFormFooter}>
                  <Button
                    type="button"
                    variant="primary"
                    size="sm"
                    loading={uploading}
                    disabled={stagedPhotos.length === 0 || uploading}
                    onClick={handleUploadAll}
                  >
                    {stagedPhotos.length > 1
                      ? `Upload ${stagedPhotos.length} photos`
                      : 'Upload photo'}
                  </Button>
                </div>
              </div>
            )}

            {p.photos.length === 0 ? (
              <EmptyState icon="🖼" title="No photos yet" description="Upload photos for this provider." />
            ) : (
              <div className={styles.photoGrid}>
                {p.photos.map((photo) => (
                  <div key={photo.id} className={styles.photoCard}>
                    {isImageUrl(photo.storage_reference) ? (
                      <img
                        src={photo.storage_reference}
                        alt={photo.alt_text ?? photo.caption ?? 'Provider photo'}
                        className={styles.photoImg}
                      />
                    ) : (
                      <div className={styles.photoPlaceholder}>🖼</div>
                    )}
                    <div className={styles.photoMeta}>
                      {photo.is_thumbnail && <Badge variant="info" size="sm">Thumbnail</Badge>}
                      {photo.caption && <p className={styles.photoCaption}>{photo.caption}</p>}
                      {photo.alt_text && <p className={styles.photoAlt}>Alt: {photo.alt_text}</p>}
                      <div className={styles.photoActions}>
                        {!photo.is_thumbnail && (
                          <Button
                            variant="outline"
                            size="sm"
                            disabled={busy}
                            onClick={() =>
                              run(() => setProviderThumbnail(p.id, photo.id), 'Failed to set thumbnail.')
                            }
                          >
                            Set thumbnail
                          </Button>
                        )}
                        <button
                          type="button"
                          className={styles.removeBtn}
                          disabled={busy}
                          onClick={() => {
                          openConfirm(
                            'Remove photo?',
                            'This photo will be permanently deleted.',
                            () => run(() => deleteProviderPhoto(p.id, photo.id), 'Failed to remove photo.')
                          );
                          }}
                        >
                          🗑 Remove
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardBody>
        </Card>
      </div>

      <ConfirmDialog
        open={confirmOpen}
        title={confirmProps.title}
        message={confirmProps.message}
        confirmLabel="Remove"
        danger={confirmProps.danger}
        onConfirm={() => {
          setConfirmOpen(false);
          confirmProps.onConfirm();
        }}
        onCancel={() => setConfirmOpen(false)}
      />
    </div>
  );
}
