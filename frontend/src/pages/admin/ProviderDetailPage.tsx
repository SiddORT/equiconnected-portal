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
  updateProviderPublication,
  updateProviderStatus,
  uploadProviderPhoto,
} from '@/api/providers';
import { listSpecializations } from '@/api/specializations';
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
  address_line_1: string;
  address_line_2: string;
  city: string;
  state_province: string;
  country: string;
  postal_code: string;
  is_primary: boolean;
}

const EMPTY_LOCATION_FORM: LocationFormValues = {
  address_line_1: '',
  address_line_2: '',
  city: '',
  state_province: '',
  country: '',
  postal_code: '',
  is_primary: false,
};

interface PhotoFormValues {
  alt_text: string;
  caption: string;
}

const EMPTY_PHOTO_FORM: PhotoFormValues = { alt_text: '', caption: '' };

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
  const [photoForm, setPhotoForm] = useState<PhotoFormValues>(EMPTY_PHOTO_FORM);
  const [photoFile, setPhotoFile] = useState<File | null>(null);
  const [photoPreview, setPhotoPreview] = useState<string>('');
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

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setPhotoFile(file);
    const reader = new FileReader();
    reader.onload = (ev) => {
      setPhotoPreview(ev.target?.result as string);
    };
    reader.readAsDataURL(file);
  }

  function resetPhotoForm() {
    setPhotoForm(EMPTY_PHOTO_FORM);
    setPhotoFile(null);
    setPhotoPreview('');
    if (fileInputRef.current) fileInputRef.current.value = '';
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
                  {p.visit_stability === 'STABLE_VISIT' ? 'Stable visit' : 'Not stable visit'}
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
                      address_line_1: locationForm.address_line_1.trim(),
                      address_line_2: locationForm.address_line_2.trim() || null,
                      city: locationForm.city.trim(),
                      state_province: locationForm.state_province.trim() || null,
                      country: locationForm.country.trim() || null,
                      postal_code: locationForm.postal_code.trim() || null,
                      is_primary: locationForm.is_primary,
                    });
                    setLocationForm(EMPTY_LOCATION_FORM);
                    setLocationFormOpen(false);
                  }, 'Failed to add location.');
                }}
              >
                <div className={styles.formGrid}>
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
                    <div className={styles.itemMain}>
                      <span className={styles.itemTitle}>
                        {loc.address_line_1}
                        {loc.address_line_2 ? `, ${loc.address_line_2}` : ''}
                      </span>
                      <span className={styles.itemSub}>
                        {[loc.city, loc.state_province, loc.country, loc.postal_code]
                          .filter(Boolean)
                          .join(', ')}
                      </span>
                    </div>
                    <div className={styles.itemActions}>
                      {loc.is_primary && <Badge variant="info" size="sm">Primary</Badge>}
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
                {photoFormOpen ? 'Cancel' : '＋ Add photo'}
              </Button>
            </div>
          </CardHeader>
          <CardBody>
            {photoFormOpen && (
              <form
                className={styles.inlineForm}
                onSubmit={(e) => {
                  e.preventDefault();
                  if (!photoFile) {
                    setActionError('Please select an image to upload.');
                    return;
                  }
                  void run(async () => {
                    await uploadProviderPhoto(p.id, photoFile, {
                      alt_text: photoForm.alt_text.trim() || null,
                      caption: photoForm.caption.trim() || null,
                    });
                    resetPhotoForm();
                    setPhotoFormOpen(false);
                  }, 'Failed to add photo.');
                }}
              >
                <div className={styles.uploadArea}>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/*"
                    className={styles.fileInput}
                    id="photo-upload"
                    onChange={handleFileChange}
                  />
                  {photoPreview ? (
                    <div className={styles.previewWrap}>
                      <img src={photoPreview} alt="Preview" className={styles.previewImg} />
                      <button
                        type="button"
                        className={styles.changePhoto}
                        onClick={() => fileInputRef.current?.click()}
                      >
                        Change photo
                      </button>
                    </div>
                  ) : (
                    <label htmlFor="photo-upload" className={styles.uploadLabel}>
                      <span className={styles.uploadIcon}>🖼</span>
                      <span>Click to select an image</span>
                      <span className={styles.uploadHint}>PNG, JPG, WebP, GIF</span>
                    </label>
                  )}
                </div>
                <div className={styles.formGrid}>
                  <Input
                    label="Alt text"
                    placeholder="Describe the image…"
                    value={photoForm.alt_text}
                    onChange={(e) => setPhotoForm((f) => ({ ...f, alt_text: e.target.value }))}
                  />
                  <Input
                    label="Caption"
                    placeholder="Optional caption…"
                    value={photoForm.caption}
                    onChange={(e) => setPhotoForm((f) => ({ ...f, caption: e.target.value }))}
                  />
                </div>
                <div className={styles.inlineFormFooter}>
                  <Button type="submit" variant="primary" size="sm" loading={busy} disabled={!photoPreview}>
                    Upload photo
                  </Button>
                </div>
              </form>
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
