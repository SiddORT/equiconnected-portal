import { act, cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import * as publicApi from '@/api/public';
import { PublicPage } from './PublicPage';
import styles from './PublicPage.module.css';

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

vi.mock('@/hooks/usePublicPageAnimations', () => ({
  usePublicPageAnimations: vi.fn(),
}));

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  window.localStorage.clear();
  window.history.replaceState(null, '', '/');
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
    const hero = screen.getByRole('heading', {
      name: 'Healthcare, Connected Around You.',
    }).closest('section') as HTMLElement;
    expect(within(hero as HTMLElement).getByRole('link', {
      name: 'Join as a provider',
    }).getAttribute('href')).toBe('/provider/signup');
    expect(screen.getByRole('region', { name: 'Equine care stories' })).toBeTruthy();
    const heroStories = screen.getByRole('region', { name: 'Equine care stories' });
    expect(within(heroStories).getByRole('img', { name: 'Dark horse standing in a quiet mountain pasture at sunset' })).toBeTruthy();
    expect(document.querySelector('#crescent-border-gradient')).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'Next image' }));
    expect(within(heroStories).getByRole('img', { name: 'Equine care professional working with a horse indoors' })).toBeTruthy();
    await waitFor(() => expect(publicApi.recordPublicVisit).toHaveBeenCalledOnce());
  });

  it('auto-advances the homepage hero without changing its accessible active image', () => {
    vi.useFakeTimers();
    render(<MemoryRouter><PublicPage /></MemoryRouter>);

    const heroStories = screen.getByRole('region', { name: 'Equine care stories' });
    expect(within(heroStories).getByRole('img', {
      name: 'Dark horse standing in a quiet mountain pasture at sunset',
    })).toBeTruthy();

    act(() => vi.advanceTimersByTime(5600));

    expect(within(heroStories).getByRole('img', {
      name: 'Equine care professional working with a horse indoors',
    })).toBeTruthy();
    expect(within(heroStories).getByRole('button', {
      name: 'Show image 2: Expertise, connected',
    }).getAttribute('aria-pressed')).toBe('true');
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

  it('uses full-width action groups while preserving conversion destinations', () => {
    render(<MemoryRouter><PublicPage /></MemoryRouter>);

    const hero = screen.getByRole('heading', {
      name: 'Healthcare, Connected Around You.',
    }).closest('section') as HTMLElement;
    const heroActions = hero.querySelector(`.${styles.ctas}`) as HTMLElement;
    expect(heroActions).toBeTruthy();
    expect(heroActions.classList.contains(styles.ctas)).toBe(true);
    expect(Array.from(heroActions.querySelectorAll('a')).map((link) => link.getAttribute('href')))
      .toEqual(['/signup', '/provider/signup']);
    expect(Array.from(heroActions.querySelectorAll('a')).every((link) => (
      link.classList.contains(styles.primaryCta) || link.classList.contains(styles.secondaryCta)
    ))).toBe(true);

    const providerSection = screen.getByRole('heading', {
      name: 'Grow your presence with EquiConnected.',
    }).closest('section');

    expect(providerSection).toBeTruthy();
    const providerCta = within(providerSection as HTMLElement).getByRole('link', {
      name: /join as a provider/i,
    });
    expect(providerCta.getAttribute('href')).toBe('/provider/signup');
    expect(providerCta.classList.contains(styles.providerCta)).toBe(true);

    const finalSection = screen.getByRole('heading', {
      name: 'Your healthcare network starts here.',
    }).closest('section');
    expect(finalSection).toBeTruthy();
    const finalActions = (finalSection as HTMLElement)
      .querySelector(`.${styles.finalCtaActions}`) as HTMLElement;
    expect(finalActions).toBeTruthy();
    expect(Array.from(finalActions.querySelectorAll('a')).map((link) => link.getAttribute('href')))
      .toEqual(['/signup', '/provider/signup']);
    expect(Array.from(finalActions.querySelectorAll('a')).every((link) => (
      link.classList.contains(styles.finalPrimaryCta) || link.classList.contains(styles.finalSecondaryCta)
    ))).toBe(true);
  });

  it('removes the public specialization explorer without disrupting adjacent care content', () => {
    render(<MemoryRouter><PublicPage /></MemoryRouter>);

    expect(document.querySelector('#specializations')).toBeNull();
    expect(screen.queryByRole('heading', { name: 'A closer look at whole-horse care.' })).toBeNull();
    expect(screen.queryByRole('group', { name: 'Equine healthcare specializations' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Previous specialization' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Next specialization' })).toBeNull();
    expect(screen.queryByText(/^Selected .+/)).toBeNull();
    expect(screen.queryByRole('region', { name: 'Care, in focus.' })).toBeNull();
    expect(screen.getByRole('heading', { name: 'From concern to confident care.' })).toBeTruthy();
    expect(screen.getByRole('heading', { name: 'Healthcare is closer than you think.' })).toBeTruthy();

    const main = screen.getByRole('main');
    const hero = screen.getByRole('heading', {
      name: 'Healthcare, Connected Around You.',
    }).closest('section');
    const careJourney = screen.getByRole('heading', {
      name: 'From concern to confident care.',
    }).closest('section');
    const aboutSection = document.getElementById('about-us');
    expect(hero).toBeTruthy();
    expect(aboutSection).toBeTruthy();
    expect(careJourney).toBeTruthy();
    expect(Array.from(main.children).indexOf(aboutSection as HTMLElement))
      .toBe(Array.from(main.children).indexOf(hero as HTMLElement) + 1);
    expect(Array.from(main.children).indexOf(careJourney as HTMLElement))
      .toBe(Array.from(main.children).indexOf(aboutSection as HTMLElement) + 1);
  });

  it('renders the About Us section directly below the hero with its supplied image', () => {
    render(<MemoryRouter><PublicPage /></MemoryRouter>);

    const main = screen.getByRole('main');
    const hero = screen.getByRole('heading', {
      name: 'Healthcare, Connected Around You.',
    }).closest('section');
    const aboutSection = screen.getByRole('heading', {
      name: 'Care that sees the whole horse.',
    }).closest('section');

    expect(hero).toBeTruthy();
    expect(aboutSection).toBeTruthy();
    expect(aboutSection?.id).toBe('about-us');
    expect(Array.from(main.children).indexOf(aboutSection as HTMLElement))
      .toBe(Array.from(main.children).indexOf(hero as HTMLElement) + 1);

    const aboutImage = within(aboutSection as HTMLElement).getByRole('img', {
      name: 'EquiConnected veterinary team caring for a horse',
    });
    expect(aboutImage.getAttribute('src')).toBe('/about-equiconnected-transparent.png');
    expect(within(aboutSection as HTMLElement).queryByRole('link', {
      name: /find your care network/i,
    })).toBeNull();
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

    const story = screen.getByRole('navigation', { name: 'How EquiConnected works' }).parentElement;
    if (!story) {
      throw new Error('Expected care-journey story shell to render.');
    }
    expect(story.hasAttribute('data-care-journey-story')).toBe(true);
    const rail = within(story).getByRole('navigation', { name: 'How EquiConnected works' });
    expect(rail.hasAttribute('data-care-journey-rail')).toBe(true);
    expect(rail.querySelector('[data-care-journey-rail-controls]')).toBeTruthy();
    const storyTrack = story.querySelector<HTMLElement>('[data-care-journey-track]');
    if (!storyTrack) {
      throw new Error('Expected care-journey scroll track to render.');
    }
    expect(storyTrack.querySelector('[data-care-journey-viewport]')).toBeTruthy();

    const steps = [
      {
        button: /01.*SEARCH/,
        heading: 'Tell us what care you’re looking for.',
        description: 'Start with the concern, specialty, or kind of support your horse needs.',
      },
      {
        button: /02.*DISCOVER/,
        heading: 'Find care near your location.',
        description: 'Explore doctors, clinics, and hospitals in the places that work for you',
      },
      {
        button: /03.*CONNECT/,
        heading: 'Choose with confidence.',
        description: 'Explore profiles, reviews, and practical information',
      },
    ];
    const panels = Array.from(document.querySelectorAll<HTMLElement>('[data-step-index]'));
    expect(panels).toHaveLength(3);

    for (const [index, step] of steps.entries()) {
      await user.click(screen.getByRole('button', { name: step.button }));

      expect(screen.getByRole('button', { name: step.button }).getAttribute('aria-current')).toBe('step');
      expect(screen.getByRole('heading', { name: step.heading })).toBeTruthy();
      expect(screen.getByText(new RegExp(step.description))).toBeTruthy();
      expect(panels[index].getAttribute('aria-hidden')).toBe('false');
      expect(panels[index].getAttribute('tabindex')).toBe('0');
      panels.forEach((panel, panelIndex) => {
        if (panelIndex !== index) {
          expect(panel.getAttribute('aria-hidden')).toBe('true');
          expect(panel.getAttribute('tabindex')).toBe('-1');
        }
      });
    }
  });

  it('explains the product advantages and continues into the provider journey', () => {
    render(<MemoryRouter><PublicPage /></MemoryRouter>);

    expect(screen.getByRole('heading', { name: 'The right care starts with a clearer picture.' })).toBeTruthy();
    expect(screen.getByText('Location-first discovery')).toBeTruthy();
    expect(screen.getByText('Find relevant care around you.')).toBeTruthy();
    expect(screen.getByText('Specialization-based search')).toBeTruthy();
    expect(screen.getByText('Start with the type of care you need.')).toBeTruthy();
    expect(screen.getByText('Real community insight')).toBeTruthy();
    expect(screen.getByText('Explore ratings, reviews and comments.')).toBeTruthy();
    expect(screen.getByText('One connected platform')).toBeTruthy();
    expect(screen.getByText('Doctors, clinics and hospitals in one ecosystem.')).toBeTruthy();

    expect(screen.queryByRole('heading', { name: 'Real experiences. Better decisions.' })).toBeNull();
    expect(screen.queryByText('Reviews / Community')).toBeNull();
    expect(screen.queryByText('Member view preview')).toBeNull();
    expect(screen.queryByText('Illustrative')).toBeNull();
    expect(screen.queryByText('4.8')).toBeNull();
    expect(screen.queryByText('126 community reviews')).toBeNull();
    expect(screen.queryByText(/No live review text is shown here/)).toBeNull();
    expect(screen.queryByRole('link', { name: /Explore providers/ })).toBeNull();
    const providerSection = screen.getByRole('heading', {
      name: 'Grow your presence with EquiConnected.',
    }).closest('section');

    expect(providerSection).toBeTruthy();
    expect(within(providerSection as HTMLElement).getByText('Doctors')).toBeTruthy();
    expect(within(providerSection as HTMLElement).getByText('Clinics')).toBeTruthy();
    expect(within(providerSection as HTMLElement).getByText('Hospitals')).toBeTruthy();
    expect(screen.queryByRole('heading', { name: 'Designed around better healthcare discovery.' })).toBeNull();
    expect(screen.queryByText('A clearer way to discover care')).toBeNull();
    expect(screen.queryByText('Clear provider information')).toBeNull();
    expect(screen.queryByText('Transparent community reviews')).toBeNull();
    expect(screen.queryByText('Location-based discovery')).toBeNull();
    expect(screen.queryByText('Secure member accounts')).toBeNull();
    expect(screen.queryByText('Provider profiles')).toBeNull();
    expect(screen.getByRole('heading', { name: 'Your healthcare network starts here.' })).toBeTruthy();
    expect(screen.getByText('Find the care you need. Discover providers around you.')).toBeTruthy();
    expect(screen.queryByText(/verified|certified/i)).toBeNull();
    expect(screen.queryByRole('heading', { name: 'Hospital Portal' })).toBeNull();
    expect(screen.queryByText('Streamlined tools for healthcare administrators and clinical teams.')).toBeNull();
  });

  it('keeps the closing journey in order and uses the working signup routes', () => {
    render(<MemoryRouter><PublicPage /></MemoryRouter>);

    const main = screen.getByRole('main');
    const finalSection = screen.getByRole('heading', {
      name: 'Your healthcare network starts here.',
    }).closest('section');
    const whySection = screen.getByRole('heading', {
      name: 'The right care starts with a clearer picture.',
    }).closest('section');
    const providerSection = screen.getByRole('heading', {
      name: 'Grow your presence with EquiConnected.',
    }).closest('section');

    const finalMotif = finalSection?.querySelector(`.${styles.connectionMotif}`);

    expect(providerSection).toBeTruthy();
    expect(finalSection).toBeTruthy();
    expect(whySection).toBeTruthy();
    const mainChildren = Array.from(main.children);
    const finalIndex = mainChildren.indexOf(finalSection as HTMLElement);
    const whyIndex = mainChildren.indexOf(whySection as HTMLElement);
    const providerIndex = mainChildren.indexOf(providerSection as HTMLElement);
    expect(whyIndex).toBe(finalIndex + 1);
    expect(finalIndex).toBeLessThan(whyIndex);
    expect(whyIndex).toBeLessThan(providerIndex);
    expect(document.querySelector('#trust-and-transparency')).toBeNull();

    expect(within(providerSection as HTMLElement).getByRole('link', {
      name: /join as a provider/i,
    }).getAttribute('href')).toBe('/provider/signup');
    expect(within(finalSection as HTMLElement).getByRole('link', {
      name: /find care/i,
    }).getAttribute('href')).toBe('/signup');
    expect(within(finalSection as HTMLElement).getByRole('link', {
      name: /join as a provider/i,
    }).getAttribute('href')).toBe('/provider/signup');
  });

  it('uses the supplied wordmark for both public home-brand links', () => {
    render(<MemoryRouter><PublicPage /></MemoryRouter>);

    const header = document.querySelector(`.${styles.header}`);
    const footer = screen.getByRole('contentinfo');
    const headerBrand = within(header as HTMLElement).getByRole('link', {
      name: 'EquiConnected home',
    });
    const footerBrand = within(footer).getByRole('link', {
      name: 'EquiConnected home',
    });

    expect(headerBrand.getAttribute('href')).toBe('/');
    expect(footerBrand.getAttribute('href')).toBe('/');
    for (const brand of [headerBrand, footerBrand]) {
      const logo = brand.querySelector('img');
      expect(logo?.getAttribute('src')).toBe('/equiconnected-wordmark.png');
      expect(logo?.getAttribute('alt')).toBe('');
      expect(logo?.getAttribute('aria-hidden')).toBe('true');
    }
  });

  it('provides grouped footer navigation with real destinations', () => {
    render(<MemoryRouter><PublicPage /></MemoryRouter>);

    const footer = screen.getByRole('contentinfo');
    expect(within(footer).getByRole('link', {
      name: 'EquiConnected home',
    }).getAttribute('href')).toBe('/');

    for (const group of ['Member', 'Provider', 'Company', 'Account']) {
      expect(within(footer).getByRole('heading', { name: group })).toBeTruthy();
    }

    expect(within(footer).getByRole('link', { name: 'Find care' }).getAttribute('href')).toBe('/signup');
    expect(within(footer).queryByRole('link', { name: 'Specializations' })).toBeNull();
    expect(within(footer).getByRole('link', { name: 'Join as a provider' }).getAttribute('href')).toBe('/provider/signup');
    expect(within(footer).getByRole('link', { name: 'Privacy' }).getAttribute('href')).toBe('/privacy-policy');
    expect(within(footer).getByRole('link', { name: 'Terms' }).getAttribute('href')).toBe('/terms-of-service');
    expect(within(footer).getByRole('link', { name: 'Member login' }).getAttribute('href')).toBe('/login');
    expect(within(footer).getByRole('link', { name: 'Provider login' }).getAttribute('href')).toBe('/provider/login');
    expect(within(footer).getByRole('link', { name: 'Admin login' }).getAttribute('href')).toBe('/admin/login');
    expect(within(footer).queryByRole('link', { name: /instagram|facebook|linkedin|twitter|x\.com/i })).toBeNull();
    expect(within(footer).getByText(`© ${new Date().getFullYear()} EquiConnected. All rights reserved.`)).toBeTruthy();
  });

  it('reveals and focuses a linked homepage section from the URL fragment', async () => {
    const scrollIntoView = vi.fn();
    Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', {
      configurable: true,
      value: scrollIntoView,
    });
    vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => {
      callback(0);
      return 1;
    });
    vi.stubGlobal('cancelAnimationFrame', vi.fn());
    window.history.replaceState(null, '', '/#why-equiconnected');

    render(<MemoryRouter><PublicPage /></MemoryRouter>);

    const heading = screen.getByRole('heading', {
      name: 'The right care starts with a clearer picture.',
    });
    await waitFor(() => expect(document.activeElement).toBe(heading));
    expect(scrollIntoView).toHaveBeenCalledOnce();
    expect(heading.getAttribute('tabindex')).toBe('-1');
  });

  it('highlights the most visible care-journey panel while scrolling', () => {
    render(<MemoryRouter><PublicPage /></MemoryRouter>);

    const story = screen.getByRole('navigation', { name: 'How EquiConnected works' }).parentElement;
    if (!story) {
      throw new Error('Expected care-journey story shell to render.');
    }
    const storyTrack = story.querySelector<HTMLElement>('[data-care-journey-track]');
    if (!storyTrack) {
      throw new Error('Expected care-journey scroll track to render.');
    }
    let storyTop = 124;
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: 1024 });
    Object.defineProperty(storyTrack, 'offsetHeight', { configurable: true, value: 1800 });
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

    storyTop = -1676;
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
