import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { extractErrorMessage } from '@/api/client';
import { useTimeSettings } from '@/app/TimeSettingsContext';
import { FeedbackModal } from '@/components/member/FeedbackModal';
import {
  deleteMemberReview, getMemberFeedbackCounts, getMemberReviewCounts, listMemberFeedback, listMemberReviews, updateMemberFeedback,
  updateMemberReview, withdrawMemberFeedback,
} from '@/api/memberFeedback';
import type { FeedbackCategory, MemberFeedbackPage, MemberReview, PlatformFeedback } from '@/api/memberFeedback';
import styles from './MemberReviewsPage.module.css';

type Tab = 'reviews' | 'feedback';
type ReviewDraft = { rating: number; comment: string };
type FeedbackDraft = { category: FeedbackCategory; subject: string; rating: number | null; message: string };

function prettyStatus(status: string) {
  return status.toLowerCase().replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}
function Rating({ value }: { value: number | null }) {
  return value ? <span className={styles.rating} aria-label={`${value} out of 5 stars`}>{Array.from({ length: 5 }, (_, i) => <span className={i < value ? styles.filledStar : ''} key={i}>★</span>)} <small>{value}.0</small></span> : <span className={styles.noRating}>No rating</span>;
}

export function MemberReviewsPage() {
  const { formatTimestamp } = useTimeSettings();
  const [tab, setTab] = useState<Tab>('reviews');
  const [page, setPage] = useState(1);
  const [reviews, setReviews] = useState<MemberFeedbackPage<MemberReview> | null>(null);
  const [feedback, setFeedback] = useState<MemberFeedbackPage<PlatformFeedback> | null>(null);
  const [reviewCount, setReviewCount] = useState<number | null>(null);
  const [feedbackCount, setFeedbackCount] = useState<number | null>(null);
  const [countErrors, setCountErrors] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionError, setActionError] = useState('');
  const [savingId, setSavingId] = useState<string | null>(null);
  const [reviewEdit, setReviewEdit] = useState<{ id: string; draft: ReviewDraft } | null>(null);
  const [feedbackEdit, setFeedbackEdit] = useState<{ id: string; draft: FeedbackDraft } | null>(null);
  const [feedbackOpen, setFeedbackOpen] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const result = tab === 'reviews' ? await listMemberReviews(page) : await listMemberFeedback(page);
      if (tab === 'reviews') {
        setReviews(result as MemberFeedbackPage<MemberReview>);
        setReviewCount(result.meta.total);
        setCountErrors((current) => current.filter((message) => !message.startsWith('Provider review')));
      } else {
        setFeedback(result as MemberFeedbackPage<PlatformFeedback>);
        setFeedbackCount(result.meta.total);
        setCountErrors((current) => current.filter((message) => !message.startsWith('System feedback')));
      }
    } catch (loadError) {
      setError(extractErrorMessage(loadError, 'Your activity could not be loaded. Please try again.'));
    } finally {
      setLoading(false);
    }
  }, [tab, page]);
  useEffect(() => { void load(); }, [load]);
  useEffect(() => {
    let active = true;
    getMemberReviewCounts().then((response) => {
      if (active) setReviewCount(response.all ?? response.total ?? Object.entries(response).reduce((sum, [key, value]) => sum + (key === 'all' ? 0 : value), 0));
    }).catch(() => {
      if (active) setCountErrors((current) => [...current.filter((message) => !message.startsWith('Provider review')), 'Provider review count is unavailable.']);
    });
    getMemberFeedbackCounts().then((response) => {
      if (active) setFeedbackCount(response.total);
    }).catch(() => {
      if (active) setCountErrors((current) => [...current.filter((message) => !message.startsWith('System feedback')), 'System feedback count is unavailable.']);
    });
    return () => { active = false; };
  }, []);

  const changeTab = (next: Tab) => { setTab(next); setPage(1); setError(''); setActionError(''); };
  const changePage = (next: number) => setPage(Math.max(1, next));

  const saveReview = async (review: MemberReview) => {
    if (!reviewEdit || savingId) return;
    if (!reviewEdit.draft.comment.trim()) { setActionError('Please add a few words before saving.'); return; }
    setSavingId(review.id); setActionError('');
    try {
      await updateMemberReview(review.id, review.version, { rating: reviewEdit.draft.rating, comment: reviewEdit.draft.comment.trim() });
      setReviewEdit(null);
      await load();
    } catch (saveError) { setActionError(extractErrorMessage(saveError, 'Your review could not be saved. Please try again.')); }
    finally { setSavingId(null); }
  };
  const saveFeedback = async (item: PlatformFeedback) => {
    if (!feedbackEdit || savingId) return;
    if (!feedbackEdit.draft.message.trim()) { setActionError('Please include your feedback before saving.'); return; }
    setSavingId(item.id); setActionError('');
    try {
      await updateMemberFeedback(item.id, item.version, { ...feedbackEdit.draft, subject: feedbackEdit.draft.subject.trim() || null, message: feedbackEdit.draft.message.trim() });
      setFeedbackEdit(null);
      await load();
    } catch (saveError) { setActionError(extractErrorMessage(saveError, 'Your feedback could not be saved. Please try again.')); }
    finally { setSavingId(null); }
  };
  const removeReview = async (item: MemberReview) => {
    if (!window.confirm(`Delete your review of ${item.provider_name}? This cannot be undone.`)) return;
    setSavingId(item.id); setActionError('');
    try { await deleteMemberReview(item.id, item.version); await load(); }
    catch (removeError) { setActionError(extractErrorMessage(removeError, 'Your review could not be deleted. Please try again.')); }
    finally { setSavingId(null); }
  };
  const withdrawFeedback = async (item: PlatformFeedback) => {
    if (!window.confirm('Withdraw this feedback? It will no longer appear in your active feedback list.')) return;
    setSavingId(item.id); setActionError('');
    try { await withdrawMemberFeedback(item.id, item.version); await load(); }
    catch (removeError) { setActionError(extractErrorMessage(removeError, 'Your feedback could not be withdrawn. Please try again.')); }
    finally { setSavingId(null); }
  };

  const data = tab === 'reviews' ? reviews : feedback;
  const items = data?.data ?? [];

  return (
    <main className={styles.page}>
      <div className={styles.pageInner}>
        <div className={styles.breadcrumb}><Link to="/profile">My account</Link><span>/</span><span>Reviews &amp; feedback</span></div>
        <header className={styles.header}>
          <div><p className={styles.eyebrow}>Your voice matters</p><h1>My Reviews &amp; Feedback</h1><p>Keep track of the experiences you have shared with our community and our team.</p></div>
          <div className={styles.headerActions}>
            <button className={styles.feedbackCta} type="button" onClick={() => setFeedbackOpen(true)}><span aria-hidden="true">+</span>Feedback on EquiConnected</button>
            <div className={styles.headerMark} aria-hidden="true"><span>EC</span><i /></div>
          </div>
        </header>
        <section className={styles.panel}>
          <div className={styles.tabs} role="tablist" aria-label="Your activity">
            <button role="tab" id="reviews-tab" aria-selected={tab === 'reviews'} aria-controls="member-activity" className={tab === 'reviews' ? styles.selectedTab : ''} onClick={() => changeTab('reviews')} type="button">Provider reviews <span>{reviewCount ?? '—'}</span></button>
            <button role="tab" id="feedback-tab" aria-selected={tab === 'feedback'} aria-controls="member-activity" className={tab === 'feedback' ? styles.selectedTab : ''} onClick={() => changeTab('feedback')} type="button">System feedback <span>{feedbackCount ?? '—'}</span></button>
          </div>
          {countErrors.length > 0 && <p className={styles.countError} role="status">{countErrors.join(' ')}</p>}
          {actionError && <div className={styles.actionError} role="alert">{actionError}<button type="button" aria-label="Dismiss message" onClick={() => setActionError('')}>×</button></div>}
          <div id="member-activity" role="tabpanel" aria-labelledby={`${tab}-tab`} className={styles.list}>
            {loading ? <div className={styles.skeletons} aria-label="Loading your activity"><i /><i /><i /></div> :
              error ? <div className={styles.state}><span className={styles.stateIcon}>!</span><h2>We could not load this list</h2><p>{error}</p><button type="button" onClick={() => void load()}>Try again</button></div> :
                !items.length ? <div className={styles.empty}><span className={styles.emptyMark} aria-hidden="true">☆</span><h2>{tab === 'reviews' ? 'No provider reviews yet' : 'No system feedback yet'}</h2><p>{tab === 'reviews' ? 'When you share an experience with a provider, it will be saved here.' : 'Notes you send privately to EquiConnected will appear here.'}</p></div> :
                  tab === 'reviews'
                    ? (items as MemberReview[]).map((item) => <article className={styles.card} key={item.id}>
                      <div className={styles.cardTop}><div><p className={styles.cardKicker}>Provider review</p><h2>{item.provider_name}</h2></div><span className={`${styles.status} ${styles[`status_${item.status.toLowerCase()}`] ?? ''}`}>{prettyStatus(item.status)}</span></div>
                      <Rating value={item.rating} />
                      {reviewEdit?.id === item.id ? <div className={styles.editor}>
                        <label>Rating<select value={reviewEdit.draft.rating} onChange={(e) => setReviewEdit({ ...reviewEdit, draft: { ...reviewEdit.draft, rating: Number(e.target.value) } })}>{[5,4,3,2,1].map((n) => <option key={n} value={n}>{n} {n === 1 ? 'star' : 'stars'}</option>)}</select></label>
                        <label>Your review<textarea rows={4} maxLength={2000} value={reviewEdit.draft.comment} onChange={(e) => setReviewEdit({ ...reviewEdit, draft: { ...reviewEdit.draft, comment: e.target.value } })} /></label>
                        <p className={styles.moderationNote}>Saving will send this review back for moderation.</p>
                        <div className={styles.cardActions}><button type="button" onClick={() => setReviewEdit(null)}>Cancel</button><button className={styles.primaryAction} type="button" disabled={savingId === item.id} onClick={() => void saveReview(item)}>{savingId === item.id ? 'Saving…' : 'Save review'}</button></div>
                      </div> : <p className={styles.comment}>{item.comment}</p>}
                      {item.member_note && <div className={styles.note}><strong>Moderator note</strong><p>{item.member_note}</p></div>}
                      {item.status === 'PENDING' && <p className={styles.moderationNote}>Your review is awaiting moderation. Only published review text appears to other members.</p>}
                      {item.status === 'REJECTED' && <p className={styles.moderationNote}>Your review was not approved. You can edit it and submit it for moderation again.</p>}
                      {item.status === 'HIDDEN' && <p className={styles.moderationNote}>This review's text is hidden from other members and only visible to you and the EquiConnected team.</p>}
                      <div className={styles.cardFooter}><div className={styles.cardDates}><time dateTime={item.created_at}>Submitted {formatTimestamp(item.created_at)}</time>{item.updated_at !== item.created_at && <time dateTime={item.updated_at}>Updated {formatTimestamp(item.updated_at)}</time>}</div>{reviewEdit?.id !== item.id && <div className={styles.cardActions}>{item.status !== 'HIDDEN' && <button type="button" onClick={() => setReviewEdit({ id: item.id, draft: { rating: item.rating, comment: item.comment } })}>Edit review</button>}<button className={styles.dangerAction} type="button" disabled={savingId === item.id} onClick={() => void removeReview(item)}>{savingId === item.id ? 'Deleting…' : 'Delete'}</button></div>}</div>
                    </article>)
                    : (items as PlatformFeedback[]).map((item) => <article className={styles.card} key={item.id}>
                      <div className={styles.cardTop}><div><p className={styles.cardKicker}>Private note to EquiConnected</p><h2>{item.subject || item.category}</h2></div><span className={`${styles.status} ${styles[`status_${item.status.toLowerCase().replace(/\s+/g, '_')}`] ?? ''}`}>{prettyStatus(item.status)}</span></div>
                      <div className={styles.feedbackMeta}><span>{item.category}</span><Rating value={item.rating} /></div>
                      {feedbackEdit?.id === item.id ? <div className={styles.editor}>
                        <label>Category<select value={feedbackEdit.draft.category} onChange={(e) => setFeedbackEdit({ ...feedbackEdit, draft: { ...feedbackEdit.draft, category: e.target.value as FeedbackCategory } })}>{['Website / App','Search & Matching','Provider Experience','Account / Profile','Technical Issue','Suggestion','Other'].map((v) => <option key={v}>{v}</option>)}</select></label>
                        <label>Subject<input maxLength={200} value={feedbackEdit.draft.subject} onChange={(e) => setFeedbackEdit({ ...feedbackEdit, draft: { ...feedbackEdit.draft, subject: e.target.value } })} /></label>
                         <label>Overall experience (optional)<select value={feedbackEdit.draft.rating ?? ''} onChange={(e) => setFeedbackEdit({ ...feedbackEdit, draft: { ...feedbackEdit.draft, rating: e.target.value === '' ? null : Number(e.target.value) } })}><option value="">No rating</option>{[5,4,3,2,1].map((rating) => <option key={rating} value={rating}>{rating} {rating === 1 ? 'star' : 'stars'}</option>)}</select></label>
                        <label>Feedback<textarea rows={4} maxLength={5000} value={feedbackEdit.draft.message} onChange={(e) => setFeedbackEdit({ ...feedbackEdit, draft: { ...feedbackEdit.draft, message: e.target.value } })} /></label>
                        <div className={styles.cardActions}><button type="button" onClick={() => setFeedbackEdit(null)}>Cancel</button><button className={styles.primaryAction} type="button" disabled={savingId === item.id} onClick={() => void saveFeedback(item)}>{savingId === item.id ? 'Saving…' : 'Save feedback'}</button></div>
                      </div> : <p className={styles.comment}>{item.message}</p>}
                      {item.member_response && <div className={styles.response}><strong>From the EquiConnected team</strong><p>{item.member_response}</p></div>}
                      {item.status === 'Pending' && <p className={styles.moderationNote}>Your note is private and can be edited or withdrawn while it is pending.</p>}
                      {item.status === 'In review' && <p className={styles.moderationNote}>The EquiConnected team is reviewing your private feedback.</p>}
                      {item.status === 'Resolved' && !item.member_response && <p className={styles.moderationNote}>The EquiConnected team has marked this feedback as resolved.</p>}
                      {item.status === 'Rejected' && <p className={styles.moderationNote}>This feedback has been reviewed and marked as rejected.</p>}
                      <div className={styles.cardFooter}><div className={styles.cardDates}><time dateTime={item.submitted_at}>Submitted {formatTimestamp(item.submitted_at)}</time>{item.updated_at !== item.submitted_at && <time dateTime={item.updated_at}>Updated {formatTimestamp(item.updated_at)}</time>}</div>{item.status === 'Pending' && feedbackEdit?.id !== item.id && <div className={styles.cardActions}><button type="button" onClick={() => setFeedbackEdit({ id: item.id, draft: { category: item.category, subject: item.subject ?? '', rating: item.rating, message: item.message } })}>Edit feedback</button><button className={styles.dangerAction} type="button" disabled={savingId === item.id} onClick={() => void withdrawFeedback(item)}>{savingId === item.id ? 'Withdrawing…' : 'Withdraw'}</button></div>}</div>
                    </article>)
            }
          </div>
          {data && data.meta.total_pages > 1 && <nav className={styles.pagination} aria-label="Activity pages"><button type="button" disabled={page <= 1 || loading} onClick={() => changePage(page - 1)}>Previous</button><span>Page {data.meta.page} of {data.meta.total_pages}</span><button type="button" disabled={page >= data.meta.total_pages || loading} onClick={() => changePage(page + 1)}>Next</button></nav>}
        </section>
      </div>
      <FeedbackModal open={feedbackOpen} onClose={() => setFeedbackOpen(false)} />
    </main>
  );
}