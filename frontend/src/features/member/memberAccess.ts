import type { UserProfile } from '@/types';

const MEMBER_ROLES = new Set(['horse_owner', 'stable_manager']);

export function hasMemberRole(user: UserProfile | null | undefined): boolean {
  const roles = user?.roles?.length ? user.roles : [user?.role ?? ''];
  return roles.some((role) => MEMBER_ROLES.has(role));
}