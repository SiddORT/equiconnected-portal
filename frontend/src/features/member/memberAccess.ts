import type { UserProfile } from '@/types';

const MEMBER_ROLES = new Set(['horse_owner', 'stable_manager']);

export function hasMemberRole(user: UserProfile | null | undefined): boolean {
  const roles = user?.roles?.length ? user.roles : [user?.role ?? ''];
  return roles.some((role) => MEMBER_ROLES.has(role));
}

export function memberDestination(
  user: UserProfile | null | undefined,
  from?: { pathname: string; search?: string; hash?: string },
): string {
  const roles = user?.roles?.length ? user.roles : [user?.role ?? ''];
  if (!hasMemberRole(user)) {
    return roles.includes('admin') ? '/admin/dashboard' : roles.includes('provider') ? '/provider/account' : '/';
  }
  if (from && (/^\/providers(?:\/[^/]+)?$/.test(from.pathname) || from.pathname === '/profile')) {
    return `${from.pathname}${from.search ?? ''}${from.hash ?? ''}`;
  }
  return '/';
}