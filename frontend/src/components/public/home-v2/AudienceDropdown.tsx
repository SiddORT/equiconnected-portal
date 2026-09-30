import { useEffect, useId, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import styles from './HomeV2.module.css';

type AudienceDropdownProps = {
  action: 'signin' | 'join';
  placement: 'navigation' | 'hero';
  onSelect?: () => void;
  resetOn?: boolean;
};

export function AudienceDropdown({ action, placement, onSelect, resetOn }: AudienceDropdownProps) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const panelId = useId();
  const label = action === 'signin' ? 'Sign in' : 'Join EquiConnected';

  useEffect(() => setOpen(false), [resetOn]);

  useEffect(() => {
    if (!open) return;
    const closeOutside = (event: Event) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    };
    const handleKey = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return;
      event.stopPropagation();
      setOpen(false);
      trigger.current?.focus();
    };
    document.addEventListener('pointerdown', closeOutside);
    document.addEventListener('focusin', closeOutside);
    document.addEventListener('keydown', handleKey);
    return () => {
      document.removeEventListener('pointerdown', closeOutside);
      document.removeEventListener('focusin', closeOutside);
      document.removeEventListener('keydown', handleKey);
    };
  }, [open]);

  return (
    <div
      ref={root}
      className={`${styles.audienceDropdown} ${placement === 'hero' ? styles.audienceHero : styles.audienceNav} ${action === 'join' && placement === 'navigation' ? styles.audienceNavJoin : ''}`}
      data-audience-dropdown
    >
      <button
        ref={trigger}
        type="button"
        className={placement === 'hero' ? styles.goldButton : action === 'join' ? styles.navJoin : styles.audienceSignIn}
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((value) => !value)}
      >
        {label} <span className={styles.audienceChevron} aria-hidden="true">⌄</span>
      </button>
      {open && (
        <div id={panelId} className={styles.audienceChoices} aria-label={`${label} as`}>
          <Link to={action === 'signin' ? '/login' : '/signup'} onClick={() => { setOpen(false); onSelect?.(); }}>
            Members <span>— horse owners &amp; stable managers</span>
          </Link>
          <Link to={action === 'signin' ? '/provider/login' : '/provider/signup'} onClick={() => { setOpen(false); onSelect?.(); }}>
            Providers <span>— vets, clinics &amp; hospitals</span>
          </Link>
        </div>
      )}
    </div>
  );
}