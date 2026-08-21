import React from 'react';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import styles from './ReviewCard.module.css';

export interface ReviewCardData {
  id: string;
  rating: number;
  comment: string;
  reviewer_name: string;
  created_at: string;
  provider_name?: string;
  reviewer_email?: string;
  comment_visible?: boolean;
}

export type ReviewCardVariant = 'admin' | 'provider';

interface ReviewCardProps<T extends ReviewCardData> {
  review: T;
  formatTimestamp: (value: string) => string;
  variant?: ReviewCardVariant;
  updating?: boolean;
  onToggleVisibility?: () => void;
}

interface ReviewCardListProps<T extends ReviewCardData>
  extends Omit<ReviewCardProps<T>, 'review' | 'updating' | 'onToggleVisibility'> {
  reviews: T[];
  updatingId?: string | null;
  onToggleVisibility?: (review: T) => void;
  emptyTitle: string;
  emptyDescription?: string;
}

function starsFor(rating: number) {
  const filled = Math.max(0, Math.min(5, Math.round(rating)));
  return `${'★'.repeat(filled)}${'☆'.repeat(5 - filled)}`;
}

export function ReviewCard<T extends ReviewCardData>({
  review,
  formatTimestamp,
  variant = 'provider',
  updating = false,
  onToggleVisibility,
}: ReviewCardProps<T>) {
  const isAdmin = variant === 'admin';
  const hasComment = review.comment.trim().length > 0;

  return (
    <article className={styles.card} data-testid="review-card">
      <header className={styles.header}>
        <div className={styles.identity}>
          {isAdmin && review.provider_name && (
            <h3 className={styles.providerName}>{review.provider_name}</h3>
          )}
          <div className={styles.reviewMeta}>
            <span>Sent by <strong className={styles.reviewerName}>{review.reviewer_name}</strong></span>
            <time dateTime={review.created_at}>
              Submitted {formatTimestamp(review.created_at)}
            </time>
          </div>
          {isAdmin && review.reviewer_email && (
            <span className={styles.email}>{review.reviewer_email}</span>
          )}
        </div>
        <div
          className={styles.rating}
          aria-label={`${review.rating} out of 5 stars`}
          title={`${review.rating} out of 5 stars`}
        >
          <span aria-hidden="true">{starsFor(review.rating)}</span>
          <span>{review.rating}/5</span>
        </div>
      </header>

      <div className={styles.commentBlock}>
        <p className={hasComment ? styles.comment : styles.noComment}>
          {hasComment ? review.comment : 'No comment provided.'}
        </p>
      </div>

      {isAdmin && (
        <footer className={styles.footer}>
          <div className={styles.moderation}>
            <Badge size="sm" variant={review.comment_visible ? 'success' : 'neutral'}>
              {review.comment_visible ? 'Visible' : 'Hidden'}
            </Badge>
            {onToggleVisibility && (
              <Button
                size="sm"
                variant={review.comment_visible ? 'outline' : 'secondary'}
                loading={updating}
                onClick={onToggleVisibility}
              >
                {review.comment_visible ? 'Hide' : 'Restore'}
              </Button>
            )}
          </div>
        </footer>
      )}
    </article>
  );
}

export function ReviewCardList<T extends ReviewCardData>({
  reviews,
  formatTimestamp,
  variant = 'provider',
  updatingId,
  onToggleVisibility,
  emptyTitle,
  emptyDescription,
}: ReviewCardListProps<T>) {
  // Provider endpoints are intentionally limited to visible reviews. Keep the
  // UI defensive as well, so an accidentally expanded payload cannot expose a
  // hidden review while the API contract is being corrected.
  const displayReviews = variant === 'provider'
    ? reviews.filter((review) => review.comment_visible !== false)
    : reviews;

  if (displayReviews.length === 0) {
    return (
      <div className={styles.empty} role="status">
        <h3>{emptyTitle}</h3>
        {emptyDescription && <p>{emptyDescription}</p>}
      </div>
    );
  }

  return (
    <div className={styles.list} data-testid="review-card-list">
      {displayReviews.map((review) => (
        <ReviewCard
          key={review.id}
          review={review}
          formatTimestamp={formatTimestamp}
          variant={variant}
          updating={updatingId === review.id}
          onToggleVisibility={onToggleVisibility ? () => onToggleVisibility(review) : undefined}
        />
      ))}
    </div>
  );
}