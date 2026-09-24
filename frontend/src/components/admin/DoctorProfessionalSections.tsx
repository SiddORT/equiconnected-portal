/**
 * Qualification management for doctor providers on the admin detail page.
 */
import { useCallback, useEffect, useState } from 'react';
import { extractErrorMessage } from '@/api/client';
import {
  addDoctorQualification,
  deleteDoctorQualification,
  getDoctor,
  updateDoctorQualification,
} from '@/api/doctors';
import { Button } from '@/components/ui/Button';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { EmptyState } from '@/components/ui/EmptyState';
import { Input } from '@/components/ui/Input';
import type {
  DoctorResponse,
  QualificationCreate,
  QualificationResponse,
  QualificationUpdate,
} from '@/types/doctor';
import styles from '@/pages/admin/ProviderDetailPage.module.css';

interface Props {
  providerId: string;
}

export function DoctorProfessionalSections({ providerId }: Props) {
  const [doctor, setDoctor] = useState<DoctorResponse | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Qualification form
  const [qualFormOpen, setQualFormOpen] = useState(false);
  const [qualEdit, setQualEdit] = useState<QualificationResponse | null>(null);
  const [qualTitle, setQualTitle] = useState('');
  const [qualInstitution, setQualInstitution] = useState('');
  const [qualYear, setQualYear] = useState('');
  const [qualDesc, setQualDesc] = useState('');

  // Confirm dialog
  const [confirm, setConfirm] = useState<{
    title: string;
    message?: string;
    onConfirm: () => void;
  } | null>(null);

  const refreshDoctor = useCallback(async (preserveCurrent = false) => {
    try {
      setDoctor(await getDoctor(providerId));
      setLoadError(null);
    } catch (err) {
      const message = extractErrorMessage(err, 'Failed to load doctor details.');
      if (preserveCurrent) {
        setActionError(message);
      } else {
        setLoadError(message);
      }
    }
  }, [providerId]);

  const load = useCallback(async () => {
    await refreshDoctor();
  }, [refreshDoctor]);

  useEffect(() => {
    setDoctor(null);
    setLoadError(null);
    void load();
  }, [load]);

  async function runQualificationMutation(
    action: () => Promise<void>,
    failMessage: string
  ) {
    setBusy(true);
    setActionError(null);
    try {
      await action();
      // Keep the confirmed local result visible if a follow-up read is
      // temporarily unavailable.
      await refreshDoctor(true);
    } catch (err) {
      setActionError(extractErrorMessage(err, failMessage));
    } finally {
      setBusy(false);
    }
  }

  function openNewQual() {
    setQualEdit(null);
    setQualTitle('');
    setQualInstitution('');
    setQualYear('');
    setQualDesc('');
    setQualFormOpen(true);
  }

  function closeQualForm() {
    setQualFormOpen(false);
    setQualEdit(null);
    setQualTitle('');
    setQualInstitution('');
    setQualYear('');
    setQualDesc('');
  }

  function openEditQual(q: QualificationResponse) {
    setQualEdit(q);
    setQualTitle(q.title);
    setQualInstitution(q.institution ?? '');
    setQualYear(q.year_obtained != null ? String(q.year_obtained) : '');
    setQualDesc(q.description ?? '');
    setQualFormOpen(true);
  }

  async function handleSaveQual(e: React.FormEvent) {
    e.preventDefault();
    if (!qualTitle.trim()) {
      setActionError('Qualification title is required.');
      return;
    }
    const body: QualificationCreate | QualificationUpdate = {
      title: qualTitle.trim(),
      institution: qualInstitution.trim() || null,
      year_obtained: qualYear.trim() ? Number(qualYear) : null,
      description: qualDesc.trim() || null,
    };
    await runQualificationMutation(async () => {
      if (qualEdit) {
        const saved = await updateDoctorQualification(providerId, qualEdit.id, body);
        setDoctor((current) =>
          current
            ? {
                ...current,
                qualifications: current.qualifications.map((q) =>
                  q.id === saved.id ? saved : q
                ),
              }
            : current
        );
      } else {
        const saved = await addDoctorQualification(providerId, body as QualificationCreate);
        setDoctor((current) =>
          current
            ? { ...current, qualifications: [...current.qualifications, saved] }
            : current
        );
      }
      closeQualForm();
    }, 'Failed to save qualification.');
  }

  async function handleDeleteQual(q: QualificationResponse) {
    await runQualificationMutation(async () => {
      await deleteDoctorQualification(providerId, q.id);
      setDoctor((current) =>
        current
          ? { ...current, qualifications: current.qualifications.filter((item) => item.id !== q.id) }
          : current
      );
    }, 'Failed to delete qualification.');
  }

  if (loadError) {
    return (
      <Card padding="none" shadow="sm" className={styles.colFull}>
        <CardHeader><h2 className={styles.sectionTitle}>Qualifications</h2></CardHeader>
        <CardBody>
          <div className={styles.actionError} role="alert">{loadError}</div>
        </CardBody>
      </Card>
    );
  }

  if (!doctor) return null;

  return (
    <>
      {actionError && (
        <div className={`${styles.actionError} ${styles.colFull}`} role="alert">{actionError}</div>
      )}

      {/* ── Qualifications ─────────────────────────────────────────────── */}
      <Card padding="none" shadow="sm">
        <CardHeader>
          <div className={styles.cardHeaderRow}>
            <h2 className={styles.sectionTitle}>Qualifications</h2>
            <Button
              variant="outline"
              size="sm"
              onClick={() => (qualFormOpen ? closeQualForm() : openNewQual())}
            >
              {qualFormOpen ? 'Cancel' : '＋ Add qualification'}
            </Button>
          </div>
        </CardHeader>
        <CardBody>
          {qualFormOpen && (
            <form className={styles.inlineForm} onSubmit={handleSaveQual}>
              <div className={styles.formGrid}>
                <Input
                  label="Title"
                  required
                  placeholder="e.g. MBBS, MD, Fellowship…"
                  value={qualTitle}
                  onChange={(e) => setQualTitle(e.target.value)}
                  maxLength={300}
                />
                <Input
                  label="Institution"
                  value={qualInstitution}
                  onChange={(e) => setQualInstitution(e.target.value)}
                  maxLength={300}
                />
                <Input
                  label="Year obtained"
                  type="number"
                  min={1900}
                  max={2100}
                  value={qualYear}
                  onChange={(e) => setQualYear(e.target.value)}
                />
                <Input
                  label="Description"
                  value={qualDesc}
                  onChange={(e) => setQualDesc(e.target.value)}
                  maxLength={2000}
                />
              </div>
              <div className={styles.inlineFormFooter}>
                <Button type="submit" variant="primary" size="sm" loading={busy}>
                  {qualEdit ? 'Save changes' : 'Add qualification'}
                </Button>
              </div>
            </form>
          )}

          {doctor.qualifications.length === 0 ? (
            <EmptyState icon="🎓" title="No qualifications yet" />
          ) : (
            <ul className={styles.itemList}>
              {doctor.qualifications.map((q) => (
                <li key={q.id} className={styles.item}>
                  <div className={styles.itemMain}>
                    <span className={styles.itemTitle}>{q.title}</span>
                    <span className={styles.itemSub}>
                      {[q.institution, q.year_obtained].filter(Boolean).join(' · ') || '—'}
                      {q.description ? ` — ${q.description}` : ''}
                    </span>
                  </div>
                  <div className={styles.itemActions}>
                    <button
                      type="button"
                      className={styles.editBtn}
                      disabled={busy}
                      onClick={() => openEditQual(q)}
                    >
                      ✏ Edit
                    </button>
                    <button
                      type="button"
                      className={styles.removeBtn}
                      disabled={busy}
                      onClick={() =>
                        setConfirm({
                          title: 'Delete qualification?',
                          message: `Delete "${q.title}"? This cannot be undone.`,
                           onConfirm: () => void handleDeleteQual(q),
                        })
                      }
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

      <ConfirmDialog
        open={confirm !== null}
        title={confirm?.title ?? ''}
        message={confirm?.message}
        danger
        onConfirm={() => {
          confirm?.onConfirm();
          setConfirm(null);
        }}
        onCancel={() => setConfirm(null)}
      />
    </>
  );
}
