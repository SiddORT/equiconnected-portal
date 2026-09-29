import { useEffect, useState } from 'react';
import { removeSavedMemberProvider, saveMemberProvider } from '@/api/providers';
import { extractErrorMessage } from '@/api/client';
import styles from '@/pages/ProviderDirectoryPage.module.css';

export function SaveProviderButton({ id, name, saved, onChange }: {
  id: string; name: string; saved: boolean; onChange?: (saved: boolean) => void;
}) {
  const [isSaved, setIsSaved] = useState(saved);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { setIsSaved(saved); }, [saved, id]);

  const toggle = async () => {
    if (pending) return;
    setPending(true);
    setError(null);
    try {
      if (isSaved) await removeSavedMemberProvider(id);
      else await saveMemberProvider(id);
      setIsSaved(!isSaved);
      onChange?.(!isSaved);
    } catch (cause) {
      setError(extractErrorMessage(cause, 'Could not update saved providers. Try again.'));
    } finally {
      setPending(false);
    }
  };

  return <span className={styles.saveControl}>
    <button type="button" className={styles.saveButton} aria-pressed={isSaved} disabled={pending}
      aria-label={`${isSaved ? 'Remove' : 'Save'} ${name} ${isSaved ? 'from saved providers' : 'for later'}`}
      onClick={toggle}>{pending ? 'Updating…' : isSaved ? 'Saved ✓' : 'Save for later'}</button>
    {error && <span role="alert" className={styles.saveError}>{error}</span>}
  </span>;
}