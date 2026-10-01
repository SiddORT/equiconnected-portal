import { useEffect, useId, useRef, useState } from 'react';
import type { FormEvent, KeyboardEvent } from 'react';
import { extractErrorMessage } from '@/api/client';
import { submitPlatformFeedback } from '@/api/memberFeedback';
import type { FeedbackCategory, FeedbackPayload } from '@/api/memberFeedback';
import styles from './FeedbackModal.module.css';

const categories: FeedbackCategory[] = [
  'Website / App', 'Search & Matching', 'Provider Experience', 'Account / Profile',
  'Technical Issue', 'Suggestion', 'Other',
];

export interface FeedbackModalProps {
  open: boolean;
  onClose: () => void;
}

type FeedbackForm = Omit<FeedbackPayload, 'category'> & { category: FeedbackCategory | '' };
const initial: FeedbackForm = { category: '', subject: '', rating: null, message: '' };

function createIdempotencyKey() {
  if (typeof globalThis.crypto?.randomUUID === 'function') return globalThis.crypto.randomUUID();
  const bytes = new Uint8Array(16);
  if (typeof globalThis.crypto?.getRandomValues === 'function') globalThis.crypto.getRandomValues(bytes);
  else bytes.forEach((_, index) => { bytes[index] = Math.floor(Math.random() * 256); });
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('');
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

export function FeedbackModal({ open, onClose }: FeedbackModalProps) {
  const titleId = useId();
  const descriptionId = useId();
  const dialogRef = useRef<HTMLDivElement>(null);
  const confirmRef = useRef<HTMLDivElement>(null);
  const keepWritingRef = useRef<HTMLButtonElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const openerRef = useRef<HTMLElement | null>(null);
  const confirmTriggerRef = useRef<HTMLElement | null>(null);
  const onCloseRef = useRef(onClose);
  const dirtyRef = useRef(false);
  const sentRef = useRef(false);
  const loadingStateRef = useRef(false);
  const requestKey = useRef<string | null>(null);
  const busyRef = useRef(false);
  const [form, setForm] = useState<FeedbackForm>(initial);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [sent, setSent] = useState(false);
  const [confirmClose, setConfirmClose] = useState(false);
  const dirty = !!(form.category || form.subject?.trim() || form.message.trim() || form.rating);
  onCloseRef.current = onClose;
  dirtyRef.current = dirty;
  sentRef.current = sent;
  loadingStateRef.current = loading;
  const openConfirmation = () => {
    confirmTriggerRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    setConfirmClose(true);
  };
  const cancelConfirmation = () => {
    setConfirmClose(false);
    window.setTimeout(() => {
      if (confirmTriggerRef.current?.isConnected) confirmTriggerRef.current.focus();
    }, 0);
  };

  useEffect(() => {
    if (!open) return;
    openerRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const focusTimer = window.setTimeout(() => closeRef.current?.focus(), 0);
    const onKeyDown = (event: globalThis.KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        if (loadingStateRef.current) return;
        if (confirmRef.current) {
          cancelConfirmation();
          return;
        }
        if (dirtyRef.current && !sentRef.current) openConfirmation();
        else onCloseRef.current();
      }
      if (event.key === 'Tab' && dialogRef.current) {
        const focusScope = confirmRef.current ?? dialogRef.current;
        const focusable = Array.from(focusScope.querySelectorAll<HTMLElement>(
          'button:not([disabled]):not([tabindex="-1"]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex="0"]'
        ));
        if (!focusable.length) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
      }
    };
    document.addEventListener('keydown', onKeyDown);
    return () => {
      window.clearTimeout(focusTimer);
      document.body.style.overflow = previousOverflow;
      document.removeEventListener('keydown', onKeyDown);
      const opener = openerRef.current;
      window.setTimeout(() => {
        if (opener?.isConnected) opener.focus();
      }, 0);
    };
  }, [open]);

  useEffect(() => {
    if (confirmClose) keepWritingRef.current?.focus();
  }, [confirmClose]);

  useEffect(() => {
    if (!open) {
      setForm(initial);
      setError('');
      setSent(false);
      setConfirmClose(false);
      requestKey.current = null;
      busyRef.current = false;
    }
  }, [open]);

  if (!open) return null;

  const requestClose = () => {
    if (loading) return;
    if (dirty && !sent) openConfirmation();
    else onCloseRef.current();
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (busyRef.current) return;
    if (!form.category) {
      setError('Please choose a feedback category.');
      return;
    }
    if (!form.message.trim()) {
      setError('Please tell us a little about your experience.');
      return;
    }
    busyRef.current = true;
    setLoading(true);
    setError('');
    requestKey.current ??= createIdempotencyKey();
    try {
      await submitPlatformFeedback({ ...form, category: form.category, subject: form.subject?.trim() || null, message: form.message.trim() }, requestKey.current);
      setSent(true);
    } catch (submitError) {
      setError(extractErrorMessage(submitError, 'We could not send your feedback. Your message is still here; please try again.'));
    } finally {
      setLoading(false);
      busyRef.current = false;
    }
  };

  const onBackdrop = (event: React.MouseEvent<HTMLDivElement>) => {
    if (event.target === event.currentTarget) requestClose();
  };
  const onFormKeyDown = (event: KeyboardEvent<HTMLFormElement>) => {
    if (event.key === 'Enter' && (event.target as HTMLElement).tagName === 'INPUT') event.preventDefault();
  };
  const onRatingKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    const current = form.rating ?? 1;
    const next = event.key === 'ArrowRight' || event.key === 'ArrowUp' ? Math.min(5, current + 1)
      : event.key === 'ArrowLeft' || event.key === 'ArrowDown' ? Math.max(1, current - 1)
        : event.key === 'Home' ? 1 : event.key === 'End' ? 5 : null;
    if (next === null) return;
    event.preventDefault();
    setForm({ ...form, rating: next });
    dialogRef.current?.querySelector<HTMLButtonElement>(`[data-rating="${next}"]`)?.focus();
  };

  return (
    <div className={styles.backdrop} onMouseDown={onBackdrop}>
      <div className={styles.dialog} role="dialog" aria-modal="true" aria-labelledby={titleId} aria-describedby={descriptionId} ref={dialogRef}>
        <button ref={closeRef} className={styles.close} type="button" aria-label="Close feedback form" onClick={requestClose}>×</button>
        {sent ? (
          <div className={styles.success} role="status">
            <span className={styles.successMark} aria-hidden="true">✓</span>
            <p className={styles.eyebrow}>Feedback received</p>
            <h2 id={titleId}>Thank you for helping us improve.</h2>
            <p id={descriptionId}>Your note is private to you and the EquiConnected team.</p>
            <button type="button" className={styles.primary} onClick={() => onCloseRef.current()}>Done</button>
          </div>
        ) : (
          <>
            <p className={styles.eyebrow}>A note to our team</p>
            <h2 id={titleId}>Feedback on EquiConnected</h2>
            <p id={descriptionId} className={styles.intro}>Tell us what is working, what is not, or what would make your care journey better. This stays private.</p>
            <form onSubmit={submit} onKeyDown={onFormKeyDown} noValidate>
              <label className={styles.label} htmlFor="feedback-category">What is this about? <span>Required</span></label>
              <select id="feedback-category" value={form.category} required disabled={loading} onChange={(e) => setForm({ ...form, category: e.target.value as FeedbackCategory | '' })}>
                <option value="">Choose a category</option>
                {categories.map((category) => <option key={category}>{category}</option>)}
              </select>
              <fieldset className={styles.rating}>
                <legend>Overall experience <small>Optional</small></legend>
                <div className={styles.stars} role="radiogroup" aria-label="Overall experience rating" onKeyDown={onRatingKeyDown}>
                  {[1, 2, 3, 4, 5].map((score) => (
                    <button key={score} type="button" role="radio" data-rating={score} tabIndex={form.rating === score || (form.rating === null && score === 1) ? 0 : -1} disabled={loading} aria-checked={form.rating === score} aria-label={`${score} ${score === 1 ? 'star' : 'stars'}`} className={form.rating && form.rating >= score ? styles.starSelected : styles.star} onClick={() => setForm({ ...form, rating: form.rating === score ? null : score })}>★</button>
                  ))}
                </div>
              </fieldset>
              <label className={styles.label} htmlFor="feedback-subject">Subject <span>Optional</span></label>
              <input id="feedback-subject" maxLength={200} value={form.subject ?? ''} disabled={loading} onChange={(e) => setForm({ ...form, subject: e.target.value })} placeholder="A short summary" />
              <label className={styles.label} htmlFor="feedback-message">Your feedback <span>Required</span></label>
              <textarea id="feedback-message" required minLength={1} maxLength={5000} rows={5} value={form.message} disabled={loading} onChange={(e) => setForm({ ...form, message: e.target.value })} placeholder="Share as much or as little as you like…" />
              <div className={styles.meta}><span>{form.message.length}/4000</span><span>Only you and our team can see this.</span></div>
              {error && <p className={styles.error} role="alert">{error}</p>}
              <div className={styles.actions}>
                <button type="button" className={styles.secondary} onClick={requestClose} disabled={loading}>Cancel</button>
                <button type="submit" className={styles.primary} disabled={loading}>{loading ? 'Sending…' : 'Send feedback'}</button>
              </div>
            </form>
            {confirmClose && <div className={styles.confirm} role="alertdialog" aria-modal="true" aria-label="Discard feedback?" ref={confirmRef}><p>Leave without sending? Your feedback will be lost.</p><button ref={keepWritingRef} type="button" onClick={cancelConfirmation}>Keep writing</button><button type="button" onClick={() => onCloseRef.current()}>Discard</button></div>}
          </>
        )}
      </div>
    </div>
  );
}