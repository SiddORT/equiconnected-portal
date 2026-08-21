import { useEffect, useState } from 'react';
import { Link, useLocation, useParams } from 'react-router-dom';
import * as providersApi from '@/api/providers';
import { extractErrorMessage } from '@/api/client';
import { useTimeSettings } from '@/app/TimeSettingsContext';
import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { Select } from '@/components/ui/Select';
import type { MemberProviderDetail } from '@/types';
import styles from './ProviderDirectoryPage.module.css';

export function MemberProviderDetailPage() {
  const { formatTimestamp } = useTimeSettings();
  const { id } = useParams<{ id: string }>();
  const location = useLocation();
  const [provider, setProvider] = useState<MemberProviderDetail | null>(null);
  const [rating, setRating] = useState('5');
  const [comment, setComment] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState<{ kind: 'success' | 'error'; text: string } | null>(null);

  const load = async () => {
    if (!id) return;
    setLoading(true);
    try {
      const detail = await providersApi.getMemberProvider(id);
      setProvider(detail);
      setRating(String(detail.own_review?.rating ?? 5));
      setComment(detail.own_review?.comment ?? '');
    } catch (error) {
      setNotice({ kind: 'error', text: extractErrorMessage(error, 'Provider details could not be loaded.') });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, [id]);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!id) return;
    if (comment.length > 2000) {
      setNotice({ kind: 'error', text: 'Comments must be 2,000 characters or fewer.' });
      return;
    }
    setSaving(true);
    setNotice(null);
    try {
      await providersApi.saveMemberProviderReview(id, { rating: Number(rating), comment: comment.trim() });
      await load();
      setNotice({ kind: 'success', text: 'Your review has been saved.' });
    } catch (error) {
      setNotice({ kind: 'error', text: extractErrorMessage(error, 'Your review could not be saved.') });
    } finally {
      setSaving(false);
    }
  };

  const back = `/providers${location.search}`;
  if (loading) return <main className={styles.page}><div className={styles.loading} role="status"><LoadingSpinner /> <span>Loading provider…</span></div></main>;
  if (!provider) return <main className={styles.page}><Alert variant="error">{notice?.text ?? 'Provider not found.'}</Alert><Link to={back} className={styles.profileLink}>Back to providers</Link></main>;

  const locationName = provider.location
    ? [provider.location.city, provider.location.state_province, provider.location.country].filter(Boolean).join(', ')
    : 'Location details unavailable';

  return (
    <main className={styles.page}>
      <Link to={back} className={styles.backLink}>← Back to providers</Link>
      {notice && <Alert variant={notice.kind} onDismiss={() => setNotice(null)}>{notice.text}</Alert>}
      <header className={styles.detailHeader}>
        <div>
          <p className={styles.eyebrow}>{provider.provider_type.toLowerCase()}</p>
          <h1 className="text-display">{provider.name}</h1>
          <p>{locationName}</p>
        </div>
        <div className={styles.ratingBlock}>
          <strong>{provider.average_rating?.toFixed(1) ?? '—'} ★</strong>
          <span>{provider.review_count} review{provider.review_count === 1 ? '' : 's'}</span>
        </div>
      </header>

      <section className={styles.detailGrid}>
        <article className={styles.detailCard}>
          <h2>About this provider</h2>
          <p>{provider.description || 'No description has been added yet.'}</p>
          <dl className={styles.contactList}>
            {provider.email && <><dt>Email</dt><dd><a href={`mailto:${provider.email}`}>{provider.email}</a></dd></>}
            {provider.phone && <><dt>Phone</dt><dd><a href={`tel:${provider.phone}`}>{provider.phone}</a></dd></>}
            {provider.website && <><dt>Website</dt><dd><a href={provider.website} target="_blank" rel="noreferrer">Visit website</a></dd></>}
            <dt>Visit type</dt><dd>{provider.visit_stability === 'STABLE_VISIT' ? 'Stable visits available' : 'Not a stable-visit provider'}</dd>
          </dl>
        </article>

        <form className={styles.reviewForm} onSubmit={submit}>
          <h2>{provider.own_review ? 'Update your review' : 'Rate this provider'}</h2>
          {provider.own_review && !provider.own_review.comment_visible && (
            <Alert variant="info">Your prior comment is currently hidden from the directory. You can still update your rating and comment.</Alert>
          )}
          <Select
            label="Rating"
            options={[5, 4, 3, 2, 1].map((value) => ({ value: String(value), label: `${value} star${value === 1 ? '' : 's'}` }))}
            value={rating}
            onChange={(event) => setRating(event.target.value)}
          />
          <label className={styles.commentLabel} htmlFor="review-comment">Comment <span>(optional)</span></label>
          <textarea id="review-comment" className={styles.commentInput} value={comment} onChange={(event) => setComment(event.target.value)} maxLength={2000} rows={6} />
          <span className={styles.characterCount}>{comment.length}/2000</span>
          <Button type="submit" loading={saving}>Save review</Button>
        </form>
      </section>

      <section className={styles.comments}>
        <h2>Member comments</h2>
        {provider.visible_reviews.length ? provider.visible_reviews.map((review) => (
          <article className={styles.commentCard} key={review.id}>
            <div><strong>{review.reviewer_name}</strong><span className={styles.stars}>★ {review.rating.toFixed(1)}</span></div>
            <p>{review.comment}</p>
            <time dateTime={review.created_at}>{formatTimestamp(review.created_at)}</time>
          </article>
        )) : <p className={styles.noComments}>No visible comments yet. Be the first to share feedback.</p>}
      </section>
    </main>
  );
}