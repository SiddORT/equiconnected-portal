/** Presentation only: preserve API enum values and stored data. */
export function analyticsCategoryLabel(value: string): string {
  return value.split(' · ')
    .map((part) => part === 'HORSE_OWNER' ? 'Horse Owner' : part)
    .join(' · ');
}
