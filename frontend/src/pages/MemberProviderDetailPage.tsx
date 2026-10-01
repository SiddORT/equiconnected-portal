import { useCallback, useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react';
import { Link, useLocation, useParams } from 'react-router-dom';
import * as providersApi from '@/api/providers';
import { recordMemberHistory } from '@/api/memberHistoryRecording';
import {
  hasSensitiveTrafficUrlParameter,
  isNewTrafficNavigation,
  recordMemberTrafficView,
  type TrafficRouteLocation,
} from '@/analytics/trafficTracking';
import { extractErrorMessage } from '@/api/client';
import { useTimeSettings } from '@/app/TimeSettingsContext';
import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { ReviewCardList } from '@/components/reviews/ReviewCard';
import { SaveProviderButton } from '@/components/member/SaveProviderButton';
import type { MemberProviderDetail } from '@/types';
import styles from './MemberProviderDetailPage.module.css';

type Notice = { kind: 'success' | 'error' | 'info'; text: string };

function safeWebsite(value: string | null) {
  if (!value) return null;
  try {
    const url = new URL(value.trim());
    return url.protocol === 'https:' || url.protocol === 'http:' ? url.href : null;
  } catch {
    return null;
  }
}

function providerKind(kind: string) {
  return kind === 'DOCTOR' ? 'Equine doctor' : kind === 'CLINIC' ? 'Equine clinic' : 'Equine hospital';
}

function locality(location: { city?: string | null; state_province?: string | null; country?: string | null } | null | undefined) {
  return location ? [location.city, location.state_province, location.country].filter(Boolean).join(', ') : '';
}

function GalleryDialog({
  photos,
  selected,
  onSelect,
  onClose,
}: {
  photos: NonNullable<MemberProviderDetail['photos']>;
  selected: number;
  onSelect: (index: number) => void;
  onClose: () => void;
}) {
  const closeRef = useRef<HTMLButtonElement>(null);
  const previousFocus = useRef<HTMLElement | null>(null);
  useEffect(() => {
    previousFocus.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    closeRef.current?.focus();
    const onKeyDown = (event: globalThis.KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        onClose();
      }
      if (event.key === 'Tab') {
        const focusable = Array.from(document.querySelectorAll<HTMLElement>('[data-gallery-dialog] button:not([disabled]), [data-gallery-dialog] a[href]'));
        if (!focusable.length) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('keydown', onKeyDown);
      document.body.style.overflow = previousOverflow;
      previousFocus.current?.focus();
    };
  }, [onClose]);

  const photo = photos[selected];
  return (
    <div className={styles.dialogScrim} onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section className={styles.galleryDialog} role="dialog" aria-modal="true" aria-label="Provider photo gallery" data-gallery-dialog>
        <div className={styles.dialogHeader}>
          <span>{selected + 1} <span aria-hidden="true">/</span> {photos.length}</span>
          <button ref={closeRef} type="button" className={styles.dialogClose} onClick={onClose} aria-label="Close photo gallery">Close <span aria-hidden="true">×</span></button>
        </div>
        <figure className={styles.dialogFigure}>
          <img src={photo.url} alt={photo.alt_text || photo.caption || 'Provider photo'} />
          {photo.caption && <figcaption>{photo.caption}</figcaption>}
        </figure>
        {photos.length > 1 && <div className={styles.dialogThumbs} aria-label="Choose a photo">
          {photos.map((item, index) => (
            <button type="button" key={`${item.url}-${index}`} onClick={() => onSelect(index)} aria-label={`View photo ${index + 1}`} aria-pressed={selected === index}>
              <img src={item.url} alt="" />
            </button>
          ))}
        </div>}
      </section>
    </div>
  );
}

export function MemberProviderDetailPage() {
  const { formatTimestamp } = useTimeSettings();
  const { id } = useParams<{ id: string }>();
  const location = useLocation();
  const [provider, setProvider] = useState<MemberProviderDetail | null>(null);
  const [rating, setRating] = useState('5');
  const [comment, setComment] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [galleryIndex, setGalleryIndex] = useState<number | null>(null);
  const reviewRef = useRef<HTMLTextAreaElement>(null);
  const recordedProfile = useRef<string | null>(null);
  const trafficLocation = useRef<TrafficRouteLocation | null>(null);
  const activeProfileId = useRef(id);
  activeProfileId.current = id;
  const reviewSubmitting = useRef(false);
  const closeGallery = useCallback(() => setGalleryIndex(null), []);

  const load = useCallback(async (showLoading = true) => {
    if (!id) return;
    if (showLoading) {
      setLoading(true);
      setProvider(null);
      setGalleryIndex(null);
      setNotice(null);
    }
    try {
      const detail = await providersApi.getMemberProvider(id);
      setProvider(detail);
      setRating(String(detail.own_review?.rating ?? 5));
      setComment(detail.own_review?.comment ?? '');
      if (activeProfileId.current === id) {
        const currentLocation: TrafficRouteLocation = {
          key: location.key,
          pathname: location.pathname,
          search: location.search,
          hash: location.hash,
          category: 'provider_profile',
        };
        if (
          !hasSensitiveTrafficUrlParameter(location.search, location.hash)
          && isNewTrafficNavigation(trafficLocation.current, currentLocation)
        ) {
          recordMemberTrafficView('provider_profile', id);
        }
        trafficLocation.current = currentLocation;
      }
      const eventKey = `provider:${location.key}:${id}`;
      if (recordedProfile.current !== eventKey) {
        recordedProfile.current = eventKey;
        void recordMemberHistory({ event_key: eventKey, type: 'provider', provider_id: id });
      }
      return detail;
    } catch (error) {
      if (showLoading) setNotice({ kind: 'error', text: extractErrorMessage(error, 'Provider details could not be loaded.') });
      throw error;
    } finally {
      if (showLoading) setLoading(false);
    }
  }, [id, location.hash, location.key, location.pathname, location.search]);

  useEffect(() => {
    void load().catch(() => undefined);
  }, [load]);

  useEffect(() => {
    if (provider && location.hash === '#contact') {
      window.setTimeout(() => document.getElementById('contact')?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 0);
    }
  }, [provider, location.hash]);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!id || reviewSubmitting.current || provider?.own_review?.status === 'HIDDEN') return;
    const cleanComment = comment.trim();
    if (cleanComment.length > 2000) {
      setNotice({ kind: 'error', text: 'Comments must be 2,000 characters or fewer.' });
      return;
    }
    reviewSubmitting.current = true;
    setSaving(true);
    setNotice(null);
    try {
      const savedReview = await providersApi.saveMemberProviderReview(id, { rating: Number(rating), comment: cleanComment, expected_version: provider?.own_review?.version });
      setProvider(current => current ? { ...current, own_review: savedReview } : current);
      setNotice({ kind: 'success', text: 'Your review has been saved and is awaiting publication. Edits return reviews to moderation.' });
      try {
        await load(false);
      } catch {
        setNotice({ kind: 'info', text: 'Your review was saved. The displayed profile could not refresh just now; reload this page to see the latest review totals.' });
      }
    } catch (error) {
      setNotice({ kind: 'error', text: extractErrorMessage(error, 'Your review could not be saved.') });
    } finally {
      reviewSubmitting.current = false;
      setSaving(false);
    }
  };

  const fromCareNearYou = location.state?.fromCareNearYou === true;
  const back = fromCareNearYou ? '/providers' : `/providers${location.search}`;
  const directoryState = fromCareNearYou ? undefined : {
    directoryCoordinates: location.state?.directoryCoordinates,
    directoryLocationGranted: location.state?.directoryLocationGranted === true,
  };
  const backLabel = 'Back to providers';

  if (loading) return (
    <main className={styles.page}>
      <div className={styles.loadingSkeleton} role="status" aria-label="Loading provider profile">
        <span /><span /><span /><span />
      </div>
    </main>
  );
  if (!provider) return (
    <main className={styles.page}>
      <div className={styles.errorState}><p className={styles.kicker}>Profile unavailable</p><h1>We couldn’t load this provider.</h1>
        {notice && <Alert variant="error">{notice.text}</Alert>}
        <div className={styles.errorActions}><Button onClick={() => { setNotice(null); void load().catch(() => undefined); }}>Try again</Button><Link state={directoryState} to={back} className={styles.backLink}>Back to providers</Link></div>
      </div>
    </main>
  );

  const city = locality(provider.location) || 'Location details unavailable';
  const experience = provider.years_experience == null ? null : `${provider.years_experience} ${provider.years_experience === 1 ? 'year' : 'years'}`;
  const website = safeWebsite(provider.website);
  const photos = [...(provider.photos ?? [])].filter(photo => !!photo.url).sort((a, b) => (a.display_order ?? 0) - (b.display_order ?? 0));
  const selectedPhoto = photos.find(photo => photo.is_thumbnail) ?? photos.find(photo => photo.url === provider.thumbnail_url) ?? photos[0];
  const heroPhoto = selectedPhoto?.url || provider.thumbnail_url;
  const heroAlt = selectedPhoto?.alt_text || selectedPhoto?.caption || provider.thumbnail_alt_text || `${provider.name} profile photograph`;
  const qualifications = [...(provider.qualifications ?? [])].sort((a, b) => (a.display_order ?? 0) - (b.display_order ?? 0));
  const locations = provider.locations?.length ? provider.locations : provider.location ? [provider.location] : [];
  const showBackground = provider.provider_type === 'DOCTOR' && (qualifications.length > 0 || provider.years_experience != null);
  const showLocations = locations.length > 0 || provider.provider_type === 'DOCTOR';
  const reviewLabel = provider.review_count === 1 ? 'review' : 'reviews';
  const onReviewKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Escape') (event.currentTarget as HTMLTextAreaElement).blur();
  };
  const scrollToReview = () => {
    document.getElementById('write-review')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    window.setTimeout(() => reviewRef.current?.focus(), 350);
  };

  return (
    <main className={styles.page}>
      <Link state={directoryState} to={back} className={styles.backLink}><span aria-hidden="true">←</span> {backLabel}</Link>

      <nav className={styles.sectionNav} aria-label="Profile sections">
        <a href="#about">About</a>{showBackground && <a href="#qualifications">Qualifications</a>}<a href="#care">Care &amp; services</a>{showLocations && <a href="#locations">Locations</a>}<a href="#reviews">Reviews</a>{photos.length > 0 && <a href="#gallery">Gallery</a>}
      </nav>

      <section className={styles.hero} aria-labelledby="provider-name">
        <div className={styles.heroImageWrap}>
          {heroPhoto
            ? <img className={styles.heroImage} src={heroPhoto} alt={heroAlt} />
            : <div className={styles.imagePlaceholder} aria-label="No provider photo available"><span>EC</span><small>Profile photo not provided</small></div>}
          {photos.length > 0 && <button className={styles.openGallery} type="button" onClick={() => setGalleryIndex(Math.max(0, photos.indexOf(selectedPhoto!)))}>View photos <span aria-hidden="true">↗</span></button>}
        </div>
        <div className={styles.heroInfo}>
          <p className={styles.kicker}>{providerKind(provider.provider_type)}</p>
          <h1 id="provider-name">{provider.name}</h1>
          {provider.professional_title && <p className={styles.professionalTitle}>{provider.professional_title}</p>}
          <p className={styles.heroLocation}><span aria-hidden="true">⌖</span> {city}</p>
          <div className={styles.heroRating}>
            <span className={styles.goldStars} aria-label={`${provider.average_rating == null ? 'No average rating' : `${provider.average_rating.toFixed(1)} out of 5 stars`}`} aria-hidden="true">{provider.average_rating == null ? '☆☆☆☆☆' : `${'★'.repeat(Math.round(provider.average_rating))}${'☆'.repeat(5 - Math.round(provider.average_rating))}`}</span>
            <strong>{provider.average_rating?.toFixed(1) ?? '—'}</strong><span>{provider.review_count} {reviewLabel}</span>
          </div>
          <div className={styles.heroActions}>
            <a href="#contact" className={styles.primaryAction}>Contact provider <span aria-hidden="true">↗</span></a>
            <SaveProviderButton id={provider.id} name={provider.name} saved={provider.is_saved}
              onChange={saved => setProvider(current => current ? { ...current, is_saved: saved } : current)} />
          </div>
        </div>
      </section>

      <section className={styles.factsStrip} aria-label="Provider at a glance">
        <div><span>Experience</span><strong>{experience ?? 'Not recorded'}</strong></div>
        <div><span>Provider type</span><strong>{providerKind(provider.provider_type)}</strong></div>
        <div><span>Service area</span><strong>{provider.maximum_working_radius_km != null ? `Up to ${provider.maximum_working_radius_km} km` : provider.location ? city : 'Service area not recorded'}</strong></div>
        <div><span>Member rating</span><strong>{provider.average_rating?.toFixed(1) ?? 'Not rated'} <small>· {provider.review_count}</small></strong></div>
      </section>

      <div className={styles.contentLayout}>
        <div className={styles.mainColumn}>
          <section className={styles.section} id="about">
            <p className={styles.kicker}>A closer look</p><h2>About</h2>
            <p className={styles.prose}>{provider.biography || provider.description || 'This provider has not added an about description yet.'}</p>
            {provider.experience_description && <p className={styles.prose}>{provider.experience_description}</p>}
          </section>

          {showBackground && <section className={styles.section} id="qualifications">
            <p className={styles.kicker}>Background</p><h2>Qualifications &amp; experience</h2>
            {experience != null && <p className={styles.experienceLine}><strong>{experience}</strong> of recorded experience</p>}
            {qualifications.length > 0 ? <ol className={styles.qualificationList}>
              {qualifications.map((qualification, index) => <li key={`${qualification.title}-${index}`}>
                <span className={styles.qualificationMark} aria-hidden="true">0{index + 1}</span>
                <div><h3>{qualification.title}</h3>{qualification.institution && <p>{qualification.institution}</p>}
                  {qualification.year_obtained != null && <span className={styles.qualificationYear}>{qualification.year_obtained}</span>}
                  {qualification.description && <p>{qualification.description}</p>}</div>
              </li>)}
            </ol> : <p className={styles.muted}>No qualifications have been listed.</p>}
          </section>}

          <section className={styles.section} id="care">
            <p className={styles.kicker}>What is on record</p><h2>Care &amp; services</h2>
            {provider.specializations?.length ? <div className={styles.subSection}><h3>Specialties</h3><div className={styles.tagList}>{provider.specializations.map(item => <span key={item}>{item}</span>)}</div></div> : null}
            {provider.languages?.length ? <div className={styles.subSection}><h3>Languages</h3><div className={styles.tagList}>{provider.languages.map((language, index) => <span key={typeof language === 'string' ? language : language.code || index}>{typeof language === 'string' ? language : language.name}</span>)}</div></div> : null}
            <div className={styles.capabilityGrid}>
              {provider.visit_stability === 'STABLE_VISIT' && <article><span className={styles.capabilityIcon} aria-hidden="true">01</span><div><h3>Stable visits</h3><p>Stable visits are listed for this provider.</p></div></article>}
              {provider.clinic_hospital_visit != null && <article><span className={styles.capabilityIcon} aria-hidden="true">02</span><div><h3>Clinic / hospital visits</h3><p>{provider.clinic_hospital_visit ? 'Clinic or hospital visits are listed.' : 'Not listed as available.'}</p></div></article>}
              {provider.maximum_working_radius_km != null && <article><span className={styles.capabilityIcon} aria-hidden="true">03</span><div><h3>Recorded service radius</h3><p>Up to {provider.maximum_working_radius_km} km from the provider’s base.</p></div></article>}
              {provider.emergency_services_available === true && <article><span className={styles.capabilityIcon} aria-hidden="true">04</span><div><h3>Emergency services</h3><p>Emergency services are indicated in this listing. Contact the provider to confirm availability and response.</p></div></article>}
            </div>
            {!provider.specializations?.length && !provider.languages?.length && provider.visit_stability !== 'STABLE_VISIT' && provider.clinic_hospital_visit == null && provider.maximum_working_radius_km == null && provider.emergency_services_available !== true && <p className={styles.muted}>No additional care details have been provided.</p>}
          </section>

           {showLocations && <section className={styles.section} id="locations">
            <p className={styles.kicker}>Where care is based</p><h2>Locations &amp; service area</h2>
            {locations.length > 0 ? <div className={styles.locationGrid}>
              {locations.map((item, index) => <article className={styles.locationCard} key={`${locality(item)}-${index}`}>
                <span className={styles.locationIndex}>Location {String(index + 1).padStart(2, '0')}</span>
                <h3>{locality(item) || city}</h3>
                {provider.maximum_working_radius_km != null && <p>Service area recorded up to {provider.maximum_working_radius_km} km.</p>}
              </article>)}
            </div> : <p className={styles.muted}>No provider locations have been recorded.</p>}
            {provider.doctor_availability && <div className={styles.availabilityNote}><span className={styles.availabilityDot} /><p><strong>Recorded availability</strong>{provider.doctor_availability === 'ONGOING' ? 'Ongoing' : 'Visiting'}</p></div>}
            {!provider.doctor_availability && provider.provider_type === 'DOCTOR' && <p className={styles.muted}>Doctor availability has not been recorded.</p>}
            {!!provider.doctor_visits?.length && <div className={styles.visitList}><h3>Recorded visits</h3>{provider.doctor_visits.map((visit, index) => <article key={`${visit.start_date}-${index}`}>
              <time dateTime={visit.start_date}>{new Date(`${visit.start_date}T00:00:00`).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}</time>
              <span>to</span><time dateTime={visit.end_date}>{new Date(`${visit.end_date}T00:00:00`).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}</time>
              <strong>{locality(visit.location)}</strong>
             </article>)}<p className={styles.muted}>Recorded visit dates are not appointment slots. Contact the provider to confirm plans and availability.</p></div>}
          </section>}

          <section className={styles.section} id="reviews">
            <div className={styles.reviewHeading}><div><p className={styles.kicker}>Member experiences</p><h2>Reviews</h2></div>
              {provider.own_review?.status !== 'HIDDEN' && <button type="button" className={styles.writeReview} onClick={scrollToReview}>{provider.own_review ? 'Edit your review' : 'Write a review'} <span aria-hidden="true">↗</span></button>}
            </div>
            <div className={styles.reviewSummary}>
              <div className={styles.average}><strong>{provider.average_rating?.toFixed(1) ?? '—'}</strong><span className={styles.goldStars} aria-hidden="true">{provider.average_rating == null ? '☆☆☆☆☆' : `${'★'.repeat(Math.round(provider.average_rating))}${'☆'.repeat(5 - Math.round(provider.average_rating))}`}</span><small>{provider.review_count} member {reviewLabel}</small></div>
              <p>Ratings reflect member feedback recorded for this provider.</p>
            </div>
            {provider.own_review && <Alert variant="info">
              Your review: {provider.own_review.status ?? (provider.own_review.comment_visible ? 'Published' : 'Hidden')}.
              {provider.own_review.status === 'HIDDEN' ? ' Your approved rating is retained, but your comment is private and this review cannot be edited.' : ' New reviews and edits await publication.'}
              {provider.own_review.member_note && <p>{provider.own_review.member_note}</p>}
              {provider.own_review.status === 'HIDDEN' && <p>{provider.own_review.comment || 'No comment provided.'}</p>}
              <Link to="/my-reviews">Manage your reviews and feedback</Link>
            </Alert>}
            <ReviewCardList reviews={provider.visible_reviews} formatTimestamp={formatTimestamp} emptyTitle="No published comments yet." emptyDescription="Share your experience to help other horse owners and stable managers." />
            {provider.own_review?.status !== 'HIDDEN' && <form className={styles.reviewForm} id="write-review" onSubmit={submit}>
              <div><p className={styles.kicker}>Your experience</p><h3>{provider.own_review ? 'Update your review' : 'Leave a review'}</h3></div>
              <fieldset className={styles.starFieldset}>
                <legend>Your rating</legend>
                <div className={styles.starChoices}>{[1, 2, 3, 4, 5].map(value => <label key={value} className={styles.starChoice}>
                  <input type="radio" name="provider-rating" value={value} checked={rating === String(value)} onChange={() => setRating(String(value))} />
                  <span aria-hidden="true">{Number(rating) >= value ? '★' : '☆'}</span><span className={styles.srOnly}>{value} {value === 1 ? 'star' : 'stars'}</span>
                </label>)}</div>
                <span className={styles.ratingHelp} aria-live="polite">{rating} out of 5</span>
              </fieldset>
              <label className={styles.commentLabel} htmlFor="review-comment">Comment <span>(optional)</span></label>
              <textarea ref={reviewRef} id="review-comment" className={styles.commentInput} value={comment} onChange={event => setComment(event.target.value)} onKeyDown={onReviewKeyDown} maxLength={2000} rows={5} aria-describedby="review-count" />
              <span className={styles.characterCount} id="review-count">{comment.length}/2000</span>
              {notice && <div aria-live="polite"><Alert variant={notice.kind} onDismiss={() => setNotice(null)}>{notice.text}</Alert></div>}
              <Button type="submit" loading={saving}>{provider.own_review ? 'Update review' : 'Submit review'}</Button>
              <p className={styles.moderationNote}>New reviews and edits await publication. Only published comments appear above; hidden comments remain private.</p>
            </form>}
          </section>

          {photos.length > 0 && <section className={styles.section} id="gallery">
            <div className={styles.galleryHeading}><div><p className={styles.kicker}>A look around</p><h2>Gallery</h2></div><span>{photos.length} {photos.length === 1 ? 'photo' : 'photos'}</span></div>
            <div className={styles.galleryGrid}>
              {photos.map((photo, index) => <button type="button" className={`${styles.galleryItem} ${index === 0 ? styles.galleryFeature : ''}`} key={`${photo.url}-${index}`} onClick={() => setGalleryIndex(index)} aria-label={`Open photo ${index + 1}${photo.caption ? `: ${photo.caption}` : ''}`}>
                <img src={photo.url} alt={photo.alt_text || photo.caption || `${provider.name} photo ${index + 1}`} loading="lazy" />
                {photo.caption && <span>{photo.caption}</span>}
              </button>)}
            </div>
          </section>}
        </div>

        <aside className={styles.contactCard} id="contact" aria-labelledby="contact-title">
          <p className={styles.kicker}>Get in touch</p><h2 id="contact-title">Contact</h2>
          <p className={styles.contactIntro}>Use the provider’s recorded details to ask about care and availability.</p>
          <div className={styles.contactMethods}>
            {provider.phone && <a aria-label={provider.phone} href={`tel:${provider.phone}`}><span>Phone</span><strong>{provider.phone}</strong><i aria-hidden="true">↗</i></a>}
            {provider.email && <a aria-label={provider.email} href={`mailto:${provider.email}`}><span>Email</span><strong>{provider.email}</strong><i aria-hidden="true">↗</i></a>}
            {website && <a aria-label="Visit website" href={website} target="_blank" rel="noopener noreferrer"><span>Website</span><strong>Visit website</strong><i aria-hidden="true">↗</i></a>}
            {!provider.phone && !provider.email && !website && <p className={styles.muted}>No contact details have been published.</p>}
          </div>
          <div className={styles.contactBottom}><span className={styles.contactSeal} aria-hidden="true">EC</span><p>Information shown is what this provider has recorded in EquiConnected.</p></div>
        </aside>
      </div>
      {galleryIndex !== null && photos.length > 0 && <GalleryDialog photos={photos} selected={galleryIndex} onSelect={setGalleryIndex} onClose={closeGallery} />}
    </main>
  );
}