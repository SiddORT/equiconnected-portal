/**
 * FilterBar — tab-style filter groups used across admin list pages.
 * Each group renders a row of tab buttons; the active tab is highlighted.
 */
import styles from './FilterBar.module.css';

export interface FilterOption {
  value: string;
  label: string;
}

export interface FilterGroup {
  label: string;
  options: FilterOption[];
  value: string;
  onChange: (value: string) => void;
}

interface FilterBarProps {
  groups: FilterGroup[];
  className?: string;
}

export function FilterBar({ groups, className = '' }: FilterBarProps) {
  return (
    <div className={`${styles.filterBar} ${className}`}>
      {groups.map((group) => (
        <div
          key={group.label}
          className={styles.filterTabs}
          role="group"
          aria-label={group.label}
        >
          {group.options.map((opt) => (
            <button
              key={opt.value}
              type="button"
              className={`${styles.filterTab} ${group.value === opt.value ? styles['filterTab--active'] : ''}`}
              onClick={() => group.onChange(opt.value)}
              aria-pressed={group.value === opt.value}
            >
              {opt.label}
            </button>
          ))}
        </div>
      ))}
    </div>
  );
}
