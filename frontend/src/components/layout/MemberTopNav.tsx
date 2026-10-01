import { useCallback, useEffect, useId, useRef, useState } from 'react';
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '@/app/AuthContext';
import { getProfile } from '@/api/profile';
import { getRecentMemberHistory } from '@/api/memberFeedback';
import type { MemberHistoryEntry } from '@/api/memberFeedback';
import { FeedbackModal } from '@/components/member/FeedbackModal';
import { useMessageUnreadCount } from '@/components/messaging/useMessageUnreadCount';
import styles from './MemberTopNav.module.css';

const restorableSearchFilters = new Set([
  'name', 'region', 'specialization_id', 'provider_type', 'visit_stability',
  'minimum_rating', 'emergency_only', 'saved', 'sort',
]);

function formatMemberDisplayName(fullName?: string | null, email?: string | null) {
  const name = fullName?.trim();
  if (name) return name.toLocaleLowerCase().split(/\s+/).map((word) =>
    word.split(/([-'])/).map((part, index) => index % 2 === 0 && part
      ? `${part.charAt(0).toLocaleUpperCase()}${part.slice(1)}` : part).join('')
  ).join(' ');
  return email?.trim() || 'Member';
}

function roleName(roles: string[] = []) {
  const set = roles.map((r) => r.toLowerCase());
  if (set.some((r) => r.includes('stable')) && set.some((r) => r.includes('owner'))) return 'Horse owner & stable manager';
  if (set.some((r) => r.includes('stable'))) return 'Stable manager';
  return 'Horse owner';
}

export function MemberTopNav() {
  const { user, logout } = useAuth();
  const unreadMessages = useMessageUnreadCount(user?.id);
  const navigate = useNavigate();
  const location = useLocation();
  const [loggingOut, setLoggingOut] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [accountOpen, setAccountOpen] = useState(false);
  const [feedbackOpen, setFeedbackOpen] = useState(false);
  const [history, setHistory] = useState<MemberHistoryEntry[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [historyError, setHistoryError] = useState('');
  const [horseCount, setHorseCount] = useState<number | null>(null);
  const [profileLoading, setProfileLoading] = useState(true);
  const [profileError, setProfileError] = useState(false);
  const accountRef = useRef<HTMLDivElement>(null);
  const accountButtonRef = useRef<HTMLButtonElement>(null);
  const requestEpoch = useRef(0);
  const memberIdRef = useRef(user?.id ?? null);
  const navigationId = useId();
  memberIdRef.current = user?.id ?? null;
  const displayName = formatMemberDisplayName(user?.full_name, user?.email);
  const initials = displayName.split(/\s+/).slice(0, 2).map((word) => word[0]).join('').toUpperCase();

  const refreshAccountData = useCallback(async () => {
    const memberId = user?.id;
    if (!memberId) return;
    const epoch = ++requestEpoch.current;
    setProfileLoading(true);
    setHistoryLoading(true);
    const [profileResult, historyResult] = await Promise.allSettled([getProfile(), getRecentMemberHistory()]);
    if (epoch !== requestEpoch.current || memberIdRef.current !== memberId) return;
    if (profileResult.status === 'fulfilled') {
      setHorseCount(profileResult.value.horses.length);
      setProfileError(false);
    } else {
      setHorseCount(null);
      setProfileError(true);
    }
    if (historyResult.status === 'fulfilled') {
      setHistory(historyResult.value);
      setHistoryError('');
    } else {
      setHistoryError('Recent activity could not be loaded.');
    }
    setProfileLoading(false);
    setHistoryLoading(false);
  }, [user?.id]);
  const refreshAccountDataRef = useRef(refreshAccountData);
  refreshAccountDataRef.current = refreshAccountData;

  useEffect(() => {
    if (!user?.id) {
      setHistory([]);
      setHorseCount(null);
      setHistoryLoading(false);
      setProfileLoading(false);
      setHistoryError('');
      setProfileError(false);
      setAccountOpen(false);
      setFeedbackOpen(false);
      return;
    }
    void refreshAccountData();
    const onMemberChange = () => { void refreshAccountDataRef.current(); };
    window.addEventListener('member-history-changed', onMemberChange);
    window.addEventListener('member-profile-changed', onMemberChange);
    return () => {
      requestEpoch.current += 1;
      window.removeEventListener('member-history-changed', onMemberChange);
      window.removeEventListener('member-profile-changed', onMemberChange);
    };
  }, [user?.id, refreshAccountData]);

  useEffect(() => {
    if (!accountOpen) return;
    const outside = (event: MouseEvent) => {
      if (event.target instanceof Node && !accountRef.current?.contains(event.target)) setAccountOpen(false);
    };
    const key = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setAccountOpen(false);
        accountButtonRef.current?.focus();
      }
    };
    document.addEventListener('mousedown', outside);
    document.addEventListener('keydown', key);
    return () => {
      document.removeEventListener('mousedown', outside);
      document.removeEventListener('keydown', key);
    };
  }, [accountOpen]);

  const onAccountMenuKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    const items = Array.from(event.currentTarget.querySelectorAll<HTMLElement>('[role="menuitem"]:not([disabled])'));
    if (!items.length) return;
    const current = items.indexOf(document.activeElement as HTMLElement);
    let next = -1;
    if (event.key === 'ArrowDown') next = current < 0 ? 0 : (current + 1) % items.length;
    if (event.key === 'ArrowUp') next = current < 0 ? items.length - 1 : (current - 1 + items.length) % items.length;
    if (event.key === 'Home') next = 0;
    if (event.key === 'End') next = items.length - 1;
    if (next >= 0) {
      event.preventDefault();
      items[next].focus();
    }
  };

  const toggleAccountMenu = () => {
    const nextOpen = !accountOpen;
    setAccountOpen(nextOpen);
    if (nextOpen) {
      void refreshAccountData();
      window.setTimeout(() => accountRef.current?.querySelector<HTMLElement>('[role="menuitem"]:not([disabled])')?.focus(), 0);
    }
  };

  async function handleLogout() {
    if (loggingOut) return;
    setLoggingOut(true);
    requestEpoch.current += 1;
    setAccountOpen(false);
    setFeedbackOpen(false);
    setMenuOpen(false);
    setHistoryLoading(false);
    setProfileLoading(false);
    setHistoryError('');
    setProfileError(false);
    try {
      setHistory([]);
      setHorseCount(null);
      await logout();
    } finally {
      navigate('/login', { replace: true });
    }
  }
  function chooseAccountAction() {
    setAccountOpen(false);
    accountButtonRef.current?.focus();
  }

  return (
    <>
      <header className={styles.nav} role="banner">
        <div className={styles.inner}>
          <Link className={styles.brand} to="/" aria-label="EquiConnected home">
            <img src="/logo.png" alt="" className={styles.logo} />
            <span><strong>EquiConnected</strong><small>Member space</small></span>
          </Link>
          <button type="button" className={styles.menuButton} aria-label={menuOpen ? 'Close member navigation' : 'Open member navigation'} aria-controls={navigationId} aria-expanded={menuOpen} onClick={() => setMenuOpen((open) => !open)}>
            <span aria-hidden="true">{menuOpen ? '×' : <svg viewBox="0 0 20 20"><path d="M3 5h14M3 10h14M3 15h14" /></svg>}</span><span className={styles.menuLabel}>Menu</span>
          </button>
          <nav id={navigationId} className={`${styles.links} ${menuOpen ? styles.linksOpen : ''}`} aria-label="Member navigation">
            <NavLink to="/providers" className={({ isActive }) => `${styles.link} ${isActive && new URLSearchParams(location.search).get('saved') !== 'true' ? styles.active : ''}`} onClick={() => setMenuOpen(false)}>Providers</NavLink>
            <NavLink to="/member/messages" className={({ isActive }) => `${styles.link} ${isActive ? styles.active : ''}`} onClick={() => setMenuOpen(false)}>
              Messages{unreadMessages > 0 && <span className={styles.unreadBadge} aria-label={`${unreadMessages} unread messages`}>{unreadMessages > 99 ? '99+' : unreadMessages}</span>}
            </NavLink>
            <NavLink to="/profile" className={({ isActive }) => `${styles.link} ${isActive ? styles.active : ''}`} onClick={() => setMenuOpen(false)}>Profile</NavLink>
            <NavLink to="/providers?saved=true" className={({ isActive }) => `${styles.link} ${isActive && new URLSearchParams(location.search).get('saved') === 'true' ? styles.active : ''}`} onClick={() => setMenuOpen(false)}>Saved providers</NavLink>
          </nav>
          <div className={styles.account} ref={accountRef}>
            <button ref={accountButtonRef} className={styles.accountButton} type="button" aria-haspopup="menu" aria-expanded={accountOpen} aria-label={`Account menu for ${displayName}`} onClick={toggleAccountMenu} onKeyDown={(event) => {
              if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
                event.preventDefault();
                if (!accountOpen) toggleAccountMenu();
                if (event.key === 'ArrowUp') {
                  window.setTimeout(() => {
                    const items = accountRef.current?.querySelectorAll<HTMLElement>('[role="menuitem"]:not([disabled])');
                    items?.[items.length - 1]?.focus();
                  }, 0);
                }
              }
            }}>
              <span className={styles.avatar} aria-hidden="true">{initials}</span>
              <span className={styles.accountIdentity}><strong>{displayName}</strong><small>My account</small></span>
              <svg className={styles.chevron} viewBox="0 0 16 16" aria-hidden="true"><path d="m4 6 4 4 4-4" /></svg>
            </button>
            {accountOpen && <div className={styles.dropdown} role="menu" aria-label="Account" onKeyDown={onAccountMenuKeyDown}>
              <div className={styles.profileSummary}>
                <span className={styles.summaryAvatar} aria-hidden="true">{initials}</span>
                <div><strong>{displayName}</strong><span>{roleName(user?.roles)}</span><small>{profileLoading ? 'Loading horse count…' : horseCount === null ? (profileError ? 'Horse count unavailable' : 'Horse count not available') : `${horseCount} ${horseCount === 1 ? 'horse' : 'horses'} in your care`}</small></div>
              </div>
              <div className={styles.dropdownSection}>
                <div className={styles.sectionTitle}><span>Recent activity</span><Link role="menuitem" to="/history" onClick={chooseAccountAction}>View all</Link></div>
                {historyLoading ? <p className={styles.noHistory} aria-live="polite">Loading your recent activity…</p> :
                  historyError ? <p className={styles.historyError} role="alert">{historyError}<button type="button" onClick={() => void refreshAccountData()}>Retry</button></p> :
                    history.length ? history.slice(0, 3).map((entry) => entry.type === 'search'
                      ? <Link className={styles.historyItem} role="menuitem" key={entry.id} to={`/providers?${new URLSearchParams(Object.entries(entry.filters ?? {}).filter(([key, value]) => restorableSearchFilters.has(key) && value !== null).map(([key, value]) => [key, String(value)]))}`} onClick={chooseAccountAction}><span className={styles.historyIcon} aria-hidden="true">⌕</span><span><strong>Provider search</strong><small>{Object.values(entry.filters ?? {}).filter((value) => value !== null && value !== '' && value !== false).join(' · ') || 'All providers'}</small></span></Link>
                      : <Link className={styles.historyItem} role="menuitem" key={entry.id} to={entry.provider_available ? `/providers/${entry.provider_id}` : '/providers'} onClick={chooseAccountAction}><span className={styles.historyIcon} aria-hidden="true">↗</span><span><strong>{entry.provider_name}</strong><small>{entry.provider_available ? 'Viewed profile' : 'Profile no longer available'}</small></span></Link>)
                      : <p className={styles.noHistory}>Searches and provider views will appear here as you browse.</p>}
              </div>
              <div className={styles.dropdownActions}>
                <Link role="menuitem" to="/my-reviews" onClick={chooseAccountAction}><span className={styles.actionGlyph} aria-hidden="true">☆</span>My Reviews &amp; Feedback</Link>
                <button role="menuitem" type="button" onClick={() => { chooseAccountAction(); setFeedbackOpen(true); }}><span className={styles.actionGlyph} aria-hidden="true"><svg viewBox="0 0 20 20"><path d="M10 2v16M2 10h16M4.35 4.35l11.3 11.3m0-11.3-11.3 11.3" /></svg></span>Feedback on EquiConnected</button>
                <button role="menuitem" type="button" disabled={loggingOut} onClick={handleLogout}><span className={styles.actionGlyph} aria-hidden="true">↗</span>{loggingOut ? 'Signing out…' : 'Sign out'}</button>
              </div>
            </div>}
            <button type="button" className={styles.logout} onClick={handleLogout} disabled={loggingOut} aria-label="Logout" title="Sign out">
              <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M8 3H4v14h4M11 6l4 4-4 4m4-4H7" /></svg>
            </button>
          </div>
        </div>
      </header>
      <FeedbackModal open={feedbackOpen} onClose={() => setFeedbackOpen(false)} />
    </>
  );
}