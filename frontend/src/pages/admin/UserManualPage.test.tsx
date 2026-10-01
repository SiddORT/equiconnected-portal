import { cleanup, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, useNavigate } from 'react-router-dom';
import { UserManualPage } from './UserManualPage';

vi.mock('./manual/screenshots', () => ({
  manualScreenshots: {
    'public-find-care-start': [{ src: '/manual/login-screen.png', alt: 'Provider search screen', caption: 'Provider directory starting point' }],
  },
}));

afterEach(cleanup);

function renderManual(path = '/admin/user-manual') {
  return render(<MemoryRouter initialEntries={[path]}><UserManualPage /></MemoryRouter>);
}

function HashJump({ hash }: { hash: string }) {
  const navigate = useNavigate();
  return <button type="button" onClick={() => navigate(hash)}>Jump to linked topic</button>;
}

describe('UserManualPage', () => {
  it('renders the six named sections and a responsive searchable contents area', () => {
    renderManual();
    const toc = screen.getByRole('navigation', { name: 'Manual table of contents' });
    for (const title of ['Getting started', 'Admin portal', 'Provider portal', 'Member portal', 'Dashboard & Analytics', 'Troubleshooting']) {
      expect(screen.getByRole('heading', { name: title })).toBeTruthy();
      expect(within(toc).getByRole('link', { name: title })).toBeTruthy();
    }
    expect(screen.getByLabelText('Find in the manual')).toBeTruthy();
    expect(document.querySelector('.UserManualPage_module__layout') ?? document.querySelector('[class*="layout"]')).toBeTruthy();
  });

  it('searches complete topic text and offers a clear no-results state', async () => {
    const user = userEvent.setup();
    renderManual();
    const search = screen.getByRole('searchbox', { name: 'Find in the manual' });
    const toc = screen.getByRole('navigation', { name: 'Manual table of contents' });
    await user.type(search, 'provider profiles and contact information require a member account');
    expect(screen.getByRole('heading', { name: 'Choose the right starting point' })).toBeTruthy();
    expect(screen.queryByRole('heading', { name: 'Create and verify a member account' })).toBeNull();
    expect(within(toc).getByRole('link', { name: 'Choose the right starting point' })).toBeTruthy();
    expect(within(toc).queryByRole('link', { name: 'Create and verify a member account' })).toBeNull();
    await user.clear(search);
    await user.type(search, 'crystal moon');
    expect(screen.getByRole('status').textContent).toContain('No matching topics');
    expect(within(toc).queryByRole('link', { name: 'Choose the right starting point' })).toBeNull();
    expect(within(toc).getByText('No matching topics.')).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'Clear filters' }));
    expect(screen.getByRole('heading', { name: 'Choose the right starting point' })).toBeTruthy();
  });

  it('uses stable topic anchors and clears a search before following a table-of-contents link', async () => {
    const user = userEvent.setup();
    renderManual();
    const link = screen.getByRole('link', { name: 'Choose the right starting point' });
    expect(link.getAttribute('href')).toBe('#public-find-care-start');
    const search = screen.getByRole('searchbox', { name: 'Find in the manual' });
    await user.type(search, 'impossible text');
    expect((search as HTMLInputElement).value).toBe('impossible text');
    expect(link.getAttribute('href')).toBe('#public-find-care-start');
    expect(document.getElementById('public-find-care-start')).toBeNull();
    expect(screen.queryByRole('link', { name: 'Choose the right starting point' })).toBeNull();
    cleanup();
    render(<MemoryRouter initialEntries={['/admin/user-manual']}><HashJump hash="#public-find-care-start" /><UserManualPage /></MemoryRouter>);
    const searchAgain = screen.getByRole('searchbox', { name: 'Find in the manual' });
    await user.type(searchAgain, 'impossible text');
    expect(document.getElementById('public-find-care-start')).toBeNull();
    await user.click(screen.getByRole('button', { name: 'Jump to linked topic' }));
    expect((screen.getByRole('searchbox', { name: 'Find in the manual' }) as HTMLInputElement).value).toBe('');
    expect(document.getElementById('public-find-care-start')).toBeTruthy();
    const sectionLink = screen.getByRole('link', { name: 'Getting started' });
    await user.click(sectionLink);
    expect((screen.getByRole('searchbox', { name: 'Find in the manual' }) as HTMLInputElement).value).toBe('');
    expect(screen.getByRole('heading', { name: 'Choose the right starting point' })).toBeTruthy();
  });

  it('enlarges a local screenshot and closes accessibly with Escape, restoring focus', async () => {
    const user = userEvent.setup();
    renderManual();
    const trigger = screen.getByRole('button', { name: 'Enlarge image: Provider directory starting point' });
    await user.click(trigger);
    const dialog = screen.getByRole('dialog', { name: 'Enlarged manual screenshot' });
    expect(dialog.querySelector('img')?.getAttribute('src')).toBe('/manual/login-screen.png');
    expect(dialog.querySelector('img')?.getAttribute('alt')).toBe('Provider search screen');
    await user.keyboard('{Escape}');
    expect(screen.queryByRole('dialog')).toBeNull();
    await new Promise((resolve) => requestAnimationFrame(resolve));
    expect(document.activeElement).toBe(trigger);
  });

  it('keeps manual navigation compact on narrow layouts', () => {
    renderManual();
    expect(document.querySelector('main')).toBeNull();
    expect(document.querySelector('div[class*="page"]')).toBeTruthy();
    expect(document.querySelector('aside')?.className).toContain('sidebar');
    const details = document.querySelector('details');
    expect(details).toBeTruthy();
    expect(details?.querySelector('summary')?.textContent).toBe('Browse topics');
    expect(within(screen.getByRole('navigation', { name: 'Manual table of contents' })).getByRole('link', { name: 'Sign in to and leave the admin portal' })).toBeTruthy();
  });

  it('keeps the section index stable and removes author-supplied step numbers', () => {
    renderManual();
    const sectionHeading = document.getElementById('section-admin-portal');
    expect(sectionHeading?.id).toBe('section-admin-portal');
    expect(sectionHeading?.parentElement?.querySelector('[class*="sectionIndex"]')?.textContent).toBe('02');
    const firstStep = document.getElementById('admin-navigation')?.querySelector('ol li');
    expect(firstStep?.querySelector('span')?.textContent).toBe('01');
    expect(firstStep?.lastChild?.textContent?.trim()).toBe('Use Registrations to open registered member accounts.');
  });

  it('keeps section anchors safe on direct navigation, including malformed hashes', () => {
    renderManual('/admin/user-manual#section-admin-portal');
    expect(document.getElementById('section-admin-portal')).toBeTruthy();
    cleanup();
    expect(() => renderManual('/admin/user-manual#%E0%A4%A')).not.toThrow();
    expect(document.getElementById('section-troubleshooting')).toBeTruthy();
  });

  it('offers an accessible full-size image view and a return-to-fit action', async () => {
    const user = userEvent.setup();
    renderManual();
    await user.click(screen.getByRole('button', { name: 'Enlarge image: Provider directory starting point' }));
    const fullSize = screen.getByRole('button', { name: 'Show full size' });
    await user.click(fullSize);
    expect(fullSize.getAttribute('aria-pressed')).toBe('true');
    expect(document.querySelector('[class*="zoomViewport--fullSize"]')).toBeTruthy();
    const fit = screen.getByRole('button', { name: 'Fit to window' });
    await user.click(fit);
    expect(fit.getAttribute('aria-pressed')).toBe('false');
    expect(document.querySelector('[class*="zoomViewport--fullSize"]')).toBeNull();
  });
});