import type { DraftEmail } from '@/types';
import type { EmailEntry } from './MultiEmailField';

/** Suggest the invitation recipient until the provider saves their own email list. */
export function invitationEmailEntries(
  saved: DraftEmail[],
  recipientEmail: string,
  emailsEdited: boolean,
): EmailEntry[] {
  const entries: EmailEntry[] = saved.map(({ email, is_primary }) => ({
    email,
    is_primary: is_primary ?? false,
  }));
  const recipient = recipientEmail.trim();
  if (
    !emailsEdited && recipient &&
    !entries.some(({ email }) => email.trim().toLowerCase() === recipient.toLowerCase())
  ) {
    entries.push({ email: recipient, is_primary: entries.length === 0 });
  }
  return entries;
}