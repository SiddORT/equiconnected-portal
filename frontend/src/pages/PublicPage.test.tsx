import { act, cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import * as publicApi from '@/api/public';
import { PublicPage } from './PublicPage';

vi.mock('@/api/public', () => ({
  recordPublicVisit: vi.fn(() => Promise.resolve()),
  registerSubscriber: vi.fn(),
  listPublicProviders: vi.fn(() => Promise.resolve([])),
}));

vi.mock('@/app/TimeSettingsContext', () => ({
  systemCalendarDate: () => '2026-08-31',
  useTimeSettings: () => ({
    settings: { timezone: 'UTC' },
    isLoading: false,
    error: null,
  }),
}));

afterEach(() => {
  cleanup();
  window.localStorage.clear();
  vi.resetAllMocks();
  vi.unstubAllGlobals();
});

describe('PublicPage hero', () => {
  it('presents the connected-care message and existing signup destinations', async () => {
    const user = userEvent.setup();
    render(<MemoryRouter><PublicPage /></MemoryRouter>);

    expect(screen.getByRole('heading', { name: 'Healthcare, Connected Around You.' })).toBeTruthy();
    expect(screen.getByText(/Discover doctors, clinics and hospitals/)).toBeTruthy();
    expect(screen.getAllByRole('link', { name: 'Find care' })[1].getAttribute('href')).toBe('/signup');
    expect(screen.getByRole('link', { name: 'Join as a provider' }).getAttribute('href')).toBe('/provider/signup');
    expect(screen.getByRole('region', { name: 'Equine care stories' })).toBeTruthy();
    const heroStories = screen.getByRole('region', { name: 'Equine care stories' });
    expect(within(heroStories).getByRole('img', { name: 'Dark horse standing in a quiet mountain pasture at sunset' })).toBeTruthy();
    expect(document.querySelector('#crescent-border-gradient')).toBeTruthy();
    expect(screen.getByRole('heading', { name: 'A closer look at whole-horse care.' })).toBeTruthy();
    expect(screen.getByRole('group', { name: 'Equine healthcare specializations' })).toBeTruthy();
    expect(screen.getByRole('button', { name: /Cardiology/ })).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'Next image' }));
    expect(within(heroStories).getByRole('img', { name: 'Equine care professional working with a horse indoors' })).toBeTruthy();
    await waitFor(() => expect(publicApi.recordPublicVisit).toHaveBeenCalledOnce());
  });

  it('keeps the subscriber enrollment flow with validation and submission', async () => {
    const user = userEvent.setup();
    let resolveRequest: ((value: { message: string }) => void) | undefined;
    vi.mocked(publicApi.registerSubscriber).mockImplementation(
      () => new Promise((resolve) => { resolveRequest = resolve; }),
    );
    render(<MemoryRouter><PublicPage /></MemoryRouter>);

    await user.click(screen.getByRole('button', { name: 'Keep me posted' }));
    expect(screen.getByRole('alert').textContent).toContain('choose how you would like to register');
    expect(screen.getByLabelText('Register as')).toHaveProperty('required', true);
    expect(screen.getByLabelText('Register as').getAttribute('aria-invalid')).toBe('true');

    await user.selectOptions(screen.getByLabelText('Register as'), 'VET');
    await user.type(screen.getByLabelText('Email address'), 'vet@example.com');
    await user.click(screen.getByRole('button', { name: 'Keep me posted' }));
    expect(screen.getByRole('button', { name: 'Submitting…' })).toBeTruthy();
    expect(publicApi.registerSubscriber).toHaveBeenCalledWith({
      email: 'vet@example.com',
      registration_type: 'VET',
    });

    resolveRequest?.({ message: 'Thanks' });
    await waitFor(() => expect(screen.getByText(/team will be in touch soon/i)).toBeTruthy());
  });

  it('keeps specialization controls and selected state in sync', async () => {
    const user = userEvent.setup();
    render(<MemoryRouter><PublicPage /></MemoryRouter>);

    await user.click(screen.getByRole('button', { name: 'Next specialization' }));
    expect(screen.getByText('Selected Dermatology')).toBeTruthy();
    expect(screen.getByRole('button', { name: /Dermatology/ }).getAttribute('aria-pressed')).toBe('true');

    await user.click(screen.getByRole('button', { name: /Neurology/ }));
    expect(screen.getByText('Selected Neurology')).toBeTruthy();
    expect(screen.getByRole('button', { name: /Neurology/ }).getAttribute('aria-pressed')).toBe('true');
  });

  it('presents the three-step care journey with selectable content panels', async () => {
    const user = userEvent.setup();
    render(<MemoryRouter><PublicPage /></MemoryRouter>);

    expect(screen.getByRole('heading', { name: 'From concern to confident care.' })).toBeTruthy();
    expect(screen.getByRole('navigation', { name: 'How EquiConnected works' })).toBeTruthy();
    expect(screen.getByRole('button', { name: /01.*SEARCH/ })).toBeTruthy();
    expect(screen.getByRole('button', { name: /02.*DISCOVER/ })).toBeTruthy();
    expect(screen.getByRole('button', { name: /03.*CONNECT/ })).toBeTruthy();
    expect(screen.getByRole('img', { name: 'Horse standing in a quiet mountain pasture' })).toBeTruthy();

    await user.click(screen.getByRole('button', { name: /03.*CONNECT/ }));
    expect(screen.getByRole('button', { name: /03.*CONNECT/ }).getAttribute('aria-current')).toBe('step');
    expect(screen.getByRole('heading', { name: 'Choose with confidence.' })).toBeTruthy();
  });

  it('highlights the most visible care-journey panel while scrolling', () => {
    render(<MemoryRouter><PublicPage /></MemoryRouter>);

    const story = screen.getByRole('navigation', { name: 'How EquiConnected works' }).parentElement;
    if (!story) {
      throw new Error('Expected care-journey story shell to render.');
    }

    let storyTop = 124;
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: 1024 });
    Object.defineProperty(story, 'offsetHeight', { configurable: true, value: 1800 });
    vi.spyOn(story, 'getBoundingClientRect').mockImplementation(
      () => ({ top: storyTop } as DOMRect),
    );

    act(() => {
      window.dispatchEvent(new Event('scroll'));
    });
    expect(screen.getByRole('button', { name: /01.*SEARCH/ }).getAttribute('aria-current')).toBe('step');

    storyTop = -476;
    act(() => {
      window.dispatchEvent(new Event('scroll'));
    });
    expect(screen.getByRole('button', { name: /02.*DISCOVER/ }).getAttribute('aria-current')).toBe('step');

    storyTop = -1076;
    act(() => {
      window.dispatchEvent(new Event('scroll'));
    });
    expect(screen.getByRole('button', { name: /03.*CONNECT/ }).getAttribute('aria-current')).toBe('step');

    storyTop = -476;
    act(() => {
      window.dispatchEvent(new Event('scroll'));
    });
    expect(screen.getByRole('button', { name: /02.*DISCOVER/ }).getAttribute('aria-current')).toBe('step');
  });
});