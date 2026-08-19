/**
 * Doctor Detail page — /admin/doctors/:id
 * Sections: Overview | Professional Info | Qualifications |
 *           Organizations | Specializations | Locations | Photos
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { extractErrorMessage } from '@/api/client';
import {
  addDoctorOrganization,
  addDoctorQualification,
  addDoctorSpecialization,
  deleteDoctorQualification,
  getDoctor,
  removeDoctorOrganization,
  removeDoctorSpecialization,
  updateDoctor,
  updateDoctorOrganization,
  updateDoctorPublication,
  updateDoctorQualification,
  updateDoctorStatus,
} from '@/api/doctors';
import { listProviders } from '@/api/providers';
import { listSpecializations } from '@/api/specializations';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { ErrorState } from '@/components/ui/ErrorState';
import { FormField } from '@/components/ui/FormField';
import { Input } from '@/components/ui/Input';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { Select } from '@/components/ui/Select';
import { PageHeader } from '@/components/layout/PageHeader';
import type { LoadingState, Specialization } from '@/types';
import type {
  DoctorOrgResponse,
  DoctorOrganizationCreate,
  DoctorResponse,
  QualificationCreate,
  QualificationResponse,
  QualificationUpdate,
} from '@/types/doctor';
import styles from './DoctorDetailPage.module.css';

function initials(name: string) {
  return name
    .split(' ')
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? '')
    .join('');
}

export function DoctorDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [doctor, setDoctor] = useState<DoctorResponse | null>(null);
  const [loadState, setLoadState] = useState<LoadingState>('loading');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const [allSpecs, setAllSpecs] = useState<Specialization[]>([]);
  const [allOrgs, setAllOrgs] = useState<{ id: string; name: string }[]>([]);

  // ── Qualification form ────────────────────────────────────────────────────
  const [qualFormOpen, setQualFormOpen] = useState(false);
  const [qualEdit, setQualEdit] = useState<QualificationResponse | null>(null);
  const [qualTitle, setQualTitle] = useState('');
  const [qualInstitution, setQualInstitution] = useState('');
  const [qualYear, setQualYear] = useState('');
  const [qualDesc, setQualDesc] = useState('');
  const [qualOrder, setQualOrder] = useState('0');
  const [qualSaving, setQualSaving] = useState(false);
  const [qualError, setQualError] = useState<string | null>(null);

  // ── Org form ──────────────────────────────────────────────────────────────
  const [orgFormOpen, setOrgFormOpen] = useState(false);
  const [orgId, setOrgId] = useState('');
  const [orgPrimary, setOrgPrimary] = useState(false);
  const [orgSaving, setOrgSaving] = useState(false);
  const [orgError, setOrgError] = useState<string | null>(null);

  // ── Spec form ─────────────────────────────────────────────────────────────
  const [specFormOpen, setSpecFormOpen] = useState(false);
  const [selectedSpec, setSelectedSpec] = useState('');
  const [specSaving, setSpecSaving] = useState(false);
  const [specError, setSpecError] = useState<string | null>(null);

  // ── Confirm dialog ────────────────────────────────────────────────────────
  const [confirm, setConfirm] = useState<{
    title: string; description?: string; onConfirm: () => void; variant?: 'danger' | 'warning'
  } | null>(null);

  const load = useCallback(async () => {
    if (!id) return;
    setLoadState('loading');
    try {
      const [d] = await Promise.all([
        getDoctor(id),
        listSpecializations({ page_size: 200 }).then((r) => setAllSpecs(r.data)),
        listProviders({ page_size: 200 }).then((r) =>
          setAllOrgs(
            r.data
              .filter((p) => p.provider_type === 'HOSPITAL' || p.provider_type === 'CLINIC')
              .map((p) => ({ id: p.id, name: p.name }))
          )
        ),
      ]);
      setDoctor(d);
      setLoadState('success');
    } catch (err) {
      setErrorMessage(extractErrorMessage(err, 'Failed to load doctor.'));
      setLoadState('error');
    }
  }, [id]);

  useEffect(() => { void load(); }, [load]);

  // ── Toggle status / publication ───────────────────────────────────────────
  async function handleToggleStatus() {
    if (!doctor) return;
    const next = doctor.status === 'ACTIVE' ? 'INACTIVE' : 'ACTIVE';
    try { setDoctor(await updateDoctorStatus(doctor.id, next)); }
    catch (err) { setActionError(extractErrorMessage(err, 'Failed to update status.')); }
  }

  async function handleTogglePublication() {
    if (!doctor) return;
    const next = doctor.publication_status === 'PUBLISHED' ? 'UNPUBLISHED' : 'PUBLISHED';
    try { setDoctor(await updateDoctorPublication(doctor.id, next)); }
    catch (err) { setActionError(extractErrorMessage(err, 'Failed to update publication.')); }
  }

  // ── Qualifications ────────────────────────────────────────────────────────
  function openNewQual() {
    setQualEdit(null);
    setQualTitle(''); setQualInstitution(''); setQualYear('');
    setQualDesc(''); setQualOrder('0'); setQualError(null);
    setQualFormOpen(true);
  }
  function openEditQual(q: QualificationResponse) {
    setQualEdit(q);
    setQualTitle(q.title); setQualInstitution(q.institution ?? '');
    setQualYear(q.year_obtained ? String(q.year_obtained) : '');
    setQualDesc(q.description ?? ''); setQualOrder(String(q.display_order));
    setQualError(null); setQualFormOpen(true);
  }
  function cancelQual() { setQualFormOpen(false); setQualEdit(null); }

  async function handleSaveQual() {
    if (!doctor || !qualTitle.trim()) { setQualError('Title is required.'); return; }
    setQualSaving(true); setQualError(null);
    try {
      if (qualEdit) {
        const body: QualificationUpdate = { title: qualTitle.trim() };
        if (qualInstitution.trim()) body.institution = qualInstitution.trim();
        if (qualYear) body.year_obtained = Number(qualYear);
        if (qualDesc.trim()) body.description = qualDesc.trim();
        body.display_order = Number(qualOrder);
        await updateDoctorQualification(doctor.id, qualEdit.id, body);
      } else {
        const body: QualificationCreate = { title: qualTitle.trim() };
        if (qualInstitution.trim()) body.institution = qualInstitution.trim();
        if (qualYear) body.year_obtained = Number(qualYear);
        if (qualDesc.trim()) body.description = qualDesc.trim();
        body.display_order = Number(qualOrder);
        await addDoctorQualification(doctor.id, body);
      }
      setDoctor(await getDoctor(doctor.id));
      setQualFormOpen(false); setQualEdit(null);
    } catch (err) { setQualError(extractErrorMessage(err, 'Failed to save qualification.')); }
    finally { setQualSaving(false); }
  }

  function confirmDeleteQual(q: QualificationResponse) {
    setConfirm({
      title: 'Delete qualification',
      description: `Delete "${q.title}"? This cannot be undone.`,
      variant: 'danger',
      onConfirm: async () => {
        try { await deleteDoctorQualification(doctor!.id, q.id); setDoctor(await getDoctor(doctor!.id)); }
        catch (err) { setActionError(extractErrorMessage(err, 'Failed to delete qualification.')); }
      },
    });
  }

  // ── Specializations ───────────────────────────────────────────────────────
  const availableSpecs = allSpecs.filter(
    (s) => !(doctor?.specializations ?? []).some((a) => a.id === s.id)
  );

  async function handleAddSpec() {
    if (!doctor || !selectedSpec) return;
    setSpecSaving(true); setSpecError(null);
    try {
      setDoctor(await addDoctorSpecialization(doctor.id, selectedSpec));
      setSelectedSpec(''); setSpecFormOpen(false);
    } catch (err) { setSpecError(extractErrorMessage(err, 'Failed to add specialization.')); }
    finally { setSpecSaving(false); }
  }

  function confirmRemoveSpec(specId: string, name: string) {
    setConfirm({
      title: 'Remove specialization',
      description: `Remove "${name}" from this doctor?`,
      variant: 'warning',
      onConfirm: async () => {
        try { setDoctor(await removeDoctorSpecialization(doctor!.id, specId)); }
        catch (err) { setActionError(extractErrorMessage(err, 'Failed to remove specialization.')); }
      },
    });
  }

  // ── Organizations ─────────────────────────────────────────────────────────
  const linkedOrgIds = new Set((doctor?.organizations ?? []).map((o) => o.organization_id));
  const availableOrgs = allOrgs.filter((o) => !linkedOrgIds.has(o.id));

  async function handleAddOrg() {
    if (!doctor || !orgId) { setOrgError('Please select an organization.'); return; }
    setOrgSaving(true); setOrgError(null);
    try {
      const body: DoctorOrganizationCreate = { organization_id: orgId, is_primary: orgPrimary, status: 'ACTIVE' };
      setDoctor(await addDoctorOrganization(doctor.id, body));
      setOrgId(''); setOrgPrimary(false); setOrgFormOpen(false);
    } catch (err) { setOrgError(extractErrorMessage(err, 'Failed to add organization.')); }
    finally { setOrgSaving(false); }
  }

  async function handleSetPrimaryOrg(rel: DoctorOrgResponse) {
    if (!doctor) return;
    try { setDoctor(await updateDoctorOrganization(doctor.id, rel.id, { is_primary: true })); }
    catch (err) { setActionError(extractErrorMessage(err, 'Failed to set primary organization.')); }
  }

  function confirmRemoveOrg(rel: DoctorOrgResponse) {
    setConfirm({
      title: 'Remove organization',
      description: `Remove "${rel.organization.name}" from this doctor?`,
      variant: 'danger',
      onConfirm: async () => {
        try { setDoctor(await removeDoctorOrganization(doctor!.id, rel.id)); }
        catch (err) { setActionError(extractErrorMessage(err, 'Failed to remove organization.')); }
      },
    });
  }

  // ── Render ────────────────────────────────────────────────────────────────
  if (loadState === 'loading') return (
    <div className={styles.centeredPage}><LoadingSpinner size="lg" label="Loading doctor…" /></div>
  );
  if (loadState === 'error' || !doctor) return (
    <div className={styles.centeredPage}>
      <ErrorState title="Failed to load doctor" message={errorMessage ?? undefined} onRetry={load} />
    </div>
  );

  return (
    <div className={styles.shell}>
      <PageHeader
        title={doctor.name}
        subtitle={doctor.professional_title ?? 'Doctor profile'}
        breadcrumbs={[
          { label: 'Admin' },
          { label: 'Doctors', href: '/admin/doctors' },
          { label: doctor.name },
        ]}
        actions={
          <Button variant="secondary" onClick={() => navigate(`/admin/doctors/${doctor.id}/edit`)}>
            Edit
          </Button>
        }
      />

      <div className={styles.body}>
        {actionError && <div className={`${styles.actionError} ${styles.colFull}`}>{actionError}</div>}

        {/* ── Overview ───────────────────────────────────────────── */}
        <Card className={`${styles.overviewCard} ${styles.colFull}`}>
          <div className={styles.overviewHeader}>
            <div className={styles.avatarLg}>
              {doctor.thumbnail_url
                ? <img src={doctor.thumbnail_url} alt={doctor.name} className={styles.avatarLgImg} />
                : <span className={styles.avatarLgFallback}>{initials(doctor.name)}</span>
              }
            </div>
            <div className={styles.overviewInfo}>
              <h2 className={styles.overviewName}>{doctor.name}</h2>
              {doctor.professional_title && (
                <p className={styles.overviewTitle}>{doctor.professional_title}</p>
              )}
            </div>
            <div className={styles.badgeRow}>
              <Badge variant={doctor.status === 'ACTIVE' ? 'success' : 'neutral'}>
                {doctor.status === 'ACTIVE' ? 'Active' : 'Inactive'}
              </Badge>
              <Badge variant={doctor.publication_status === 'PUBLISHED' ? 'info' : 'neutral'}>
                {doctor.publication_status === 'PUBLISHED' ? 'Published' : 'Unpublished'}
              </Badge>
              <Badge variant={doctor.visit_stability === 'STABLE_VISIT' ? 'success' : 'warning'}>
                {doctor.visit_stability === 'STABLE_VISIT' ? 'Stable' : 'Not stable'}
              </Badge>
            </div>
            <div className={styles.overviewActions}>
              <Button size="sm" variant="secondary" onClick={handleToggleStatus}>
                {doctor.status === 'ACTIVE' ? 'Deactivate' : 'Activate'}
              </Button>
              <Button size="sm" variant="secondary" onClick={handleTogglePublication}>
                {doctor.publication_status === 'PUBLISHED' ? 'Unpublish' : 'Publish'}
              </Button>
            </div>
          </div>
          {doctor.website && (
            <p className={styles.overviewWebsite}>
              <a href={doctor.website} target="_blank" rel="noopener noreferrer">{doctor.website}</a>
            </p>
          )}
        </Card>

        {/* ── Professional Info ──────────────────────────────────── */}
        <Card>
          <div className={styles.cardHeaderRow}>
            <h3 className={styles.sectionTitle}>Professional Info</h3>
          </div>
          <dl className={styles.defList}>
            {doctor.years_experience != null && (
              <>
                <dt>Experience</dt>
                <dd>{doctor.years_experience} year{doctor.years_experience !== 1 ? 's' : ''}</dd>
              </>
            )}
            {doctor.biography && (
              <>
                <dt>Biography</dt>
                <dd className={styles.prose}>{doctor.biography}</dd>
              </>
            )}
            {doctor.experience_description && (
              <>
                <dt>Experience notes</dt>
                <dd className={styles.prose}>{doctor.experience_description}</dd>
              </>
            )}
            {!doctor.biography && !doctor.experience_description && doctor.years_experience == null && (
              <dd className={styles.muted}>No professional info added yet.</dd>
            )}
          </dl>
        </Card>

        {/* ── Qualifications ─────────────────────────────────────── */}
        <Card>
          <div className={styles.cardHeaderRow}>
            <h3 className={styles.sectionTitle}>Qualifications</h3>
            <Button size="sm" variant="secondary" onClick={openNewQual}>+ Add</Button>
          </div>

          {qualFormOpen && (
            <div className={styles.inlineForm}>
              <FormField label="Title *">
                <Input
                  value={qualTitle}
                  onChange={(e) => setQualTitle(e.target.value)}
                  placeholder="e.g. MBBS, MD, Fellowship in Cardiology"
                />
              </FormField>
              <div className={styles.formRow}>
                <FormField label="Institution">
                  <Input value={qualInstitution} onChange={(e) => setQualInstitution(e.target.value)} placeholder="e.g. AIIMS Delhi" />
                </FormField>
                <FormField label="Year obtained">
                  <Input type="number" value={qualYear} onChange={(e) => setQualYear(e.target.value)} placeholder="e.g. 2010" min={1900} max={2100} />
                </FormField>
                <FormField label="Display order">
                  <Input type="number" value={qualOrder} onChange={(e) => setQualOrder(e.target.value)} min={0} />
                </FormField>
              </div>
              <FormField label="Description">
                <textarea
                  className={styles.textarea}
                  value={qualDesc}
                  onChange={(e) => setQualDesc(e.target.value)}
                  placeholder="Additional notes…"
                  rows={3}
                />
              </FormField>
              {qualError && <p className={styles.fieldError}>{qualError}</p>}
              <div className={styles.formActions}>
                <Button size="sm" variant="primary" onClick={handleSaveQual} disabled={qualSaving}>
                  {qualSaving ? 'Saving…' : qualEdit ? 'Save changes' : 'Add qualification'}
                </Button>
                <Button size="sm" variant="ghost" onClick={cancelQual}>Cancel</Button>
              </div>
            </div>
          )}

          {doctor.qualifications.length === 0 && !qualFormOpen ? (
            <p className={styles.muted}>No qualifications added yet.</p>
          ) : (
            <ul className={styles.qualList}>
              {doctor.qualifications.map((q) => (
                <li key={q.id} className={styles.qualItem}>
                  <div className={styles.qualMain}>
                    <strong className={styles.qualTitle}>{q.title}</strong>
                    {q.institution && <span className={styles.qualSub}>{q.institution}</span>}
                    {q.year_obtained && <span className={styles.qualYear}>{q.year_obtained}</span>}
                  </div>
                  {q.description && <p className={styles.qualDesc}>{q.description}</p>}
                  <div className={styles.qualActions}>
                    <button className={styles.iconBtn} onClick={() => openEditQual(q)} title="Edit">✏️</button>
                    <button className={styles.iconBtn} onClick={() => confirmDeleteQual(q)} title="Delete">🗑</button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>

        {/* ── Organizations ──────────────────────────────────────── */}
        <Card>
          <div className={styles.cardHeaderRow}>
            <h3 className={styles.sectionTitle}>Organizations</h3>
            {availableOrgs.length > 0 && (
              <Button size="sm" variant="secondary" onClick={() => setOrgFormOpen(true)}>+ Add</Button>
            )}
          </div>

          {orgFormOpen && (
            <div className={styles.inlineForm}>
              <FormField label="Hospital / Clinic">
                <Select
                  value={orgId}
                  onChange={(e) => setOrgId(e.target.value)}
                  options={[
                    { value: '', label: 'Select organization…' },
                    ...availableOrgs.map((o) => ({ value: o.id, label: o.name })),
                  ]}
                />
              </FormField>
              <label className={styles.checkboxRow}>
                <input type="checkbox" checked={orgPrimary} onChange={(e) => setOrgPrimary(e.target.checked)} />
                <span>Primary organization</span>
              </label>
              {orgError && <p className={styles.fieldError}>{orgError}</p>}
              <div className={styles.formActions}>
                <Button size="sm" variant="primary" onClick={handleAddOrg} disabled={orgSaving}>
                  {orgSaving ? 'Adding…' : 'Add organization'}
                </Button>
                <Button size="sm" variant="ghost" onClick={() => { setOrgFormOpen(false); setOrgError(null); }}>Cancel</Button>
              </div>
            </div>
          )}

          {doctor.organizations.length === 0 && !orgFormOpen ? (
            <p className={styles.muted}>No organizations linked yet.</p>
          ) : (
            <ul className={styles.orgList}>
              {doctor.organizations.map((rel) => (
                <li key={rel.id} className={styles.orgItem}>
                  <div className={styles.orgMain}>
                    <Link to={`/admin/providers/${rel.organization.id}`} className={styles.orgName}>
                      {rel.organization.name}
                    </Link>
                    <span className={styles.orgType}>{rel.organization.provider_type}</span>
                    {rel.is_primary && <Badge variant="info" size="sm">Primary</Badge>}
                    <Badge variant={rel.status === 'ACTIVE' ? 'success' : 'neutral'} size="sm">
                      {rel.status}
                    </Badge>
                  </div>
                  <div className={styles.qualActions}>
                    {!rel.is_primary && (
                      <button className={styles.iconBtn} onClick={() => handleSetPrimaryOrg(rel)} title="Set as primary">⭐</button>
                    )}
                    <button className={styles.iconBtn} onClick={() => confirmRemoveOrg(rel)} title="Remove">🗑</button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>

        {/* ── Specializations ────────────────────────────────────── */}
        <Card>
          <div className={styles.cardHeaderRow}>
            <h3 className={styles.sectionTitle}>Specializations</h3>
            {availableSpecs.length > 0 && (
              <Button size="sm" variant="secondary" onClick={() => setSpecFormOpen(true)}>+ Add</Button>
            )}
          </div>

          {specFormOpen && (
            <div className={styles.inlineForm}>
              <FormField label="Specialization">
                <Select
                  value={selectedSpec}
                  onChange={(e) => setSelectedSpec(e.target.value)}
                  options={[
                    { value: '', label: 'Select specialization…' },
                    ...availableSpecs.map((s) => ({ value: s.id, label: s.name })),
                  ]}
                />
              </FormField>
              {specError && <p className={styles.fieldError}>{specError}</p>}
              <div className={styles.formActions}>
                <Button size="sm" variant="primary" onClick={handleAddSpec} disabled={specSaving}>
                  {specSaving ? 'Adding…' : 'Add specialization'}
                </Button>
                <Button size="sm" variant="ghost" onClick={() => { setSpecFormOpen(false); setSpecError(null); }}>Cancel</Button>
              </div>
            </div>
          )}

          <div className={styles.specPillGrid}>
            {doctor.specializations.map((s) => (
              <span key={s.id} className={styles.specPill}>
                {s.name}
                <button
                  className={styles.specPillRemove}
                  onClick={() => confirmRemoveSpec(s.id, s.name)}
                  title="Remove"
                >×</button>
              </span>
            ))}
            {doctor.specializations.length === 0 && !specFormOpen && (
              <p className={styles.muted}>No specializations assigned.</p>
            )}
          </div>
        </Card>

        {/* ── Contact ────────────────────────────────────────────── */}
        <Card>
          <div className={styles.cardHeaderRow}>
            <h3 className={styles.sectionTitle}>Contact</h3>
            <Button size="sm" variant="secondary" onClick={() => navigate(`/admin/doctors/${doctor.id}/edit`)}>
              Edit
            </Button>
          </div>
          <dl className={styles.defList}>
            {doctor.phones.length > 0 && (
              <>
                <dt>Phones</dt>
                <dd>
                  {doctor.phones.map((ph) => (
                    <div key={ph.id}>
                      {ph.country_code} {ph.number}
                      {ph.is_primary && <span className={styles.primaryLabel}> (primary)</span>}
                    </div>
                  ))}
                </dd>
              </>
            )}
            {doctor.emails.length > 0 && (
              <>
                <dt>Emails</dt>
                <dd>
                  {doctor.emails.map((em) => (
                    <div key={em.id}>
                      {em.email}
                      {em.is_primary && <span className={styles.primaryLabel}> (primary)</span>}
                    </div>
                  ))}
                </dd>
              </>
            )}
            {doctor.phones.length === 0 && doctor.emails.length === 0 && (
              <dd className={styles.muted}>No contact details added.</dd>
            )}
          </dl>
        </Card>
      </div>

      {/* Confirm dialog */}
      {confirm && (
        <ConfirmDialog
          open
          title={confirm.title}
          message={confirm.description}
          confirmLabel="Confirm"
          danger={confirm.variant === 'danger'}
          onConfirm={() => { confirm.onConfirm(); setConfirm(null); }}
          onCancel={() => setConfirm(null)}
        />
      )}
    </div>
  );
}
