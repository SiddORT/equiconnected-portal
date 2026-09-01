import { act, cleanup, render, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { WhyEquiConnected } from './WhyEquiConnected';

const gsapMocks = vi.hoisted(() => ({
  registerPlugin: vi.fn(),
  fromTo: vi.fn(),
  revert: vi.fn(),
}));

vi.mock('gsap', () => ({
  default: {
    registerPlugin: gsapMocks.registerPlugin,
    fromTo: gsapMocks.fromTo,
    context: vi.fn((callback: () => void) => {
      callback();
      return { revert: gsapMocks.revert };
    }),
  },
}));

vi.mock('gsap/ScrollTrigger', () => ({
  ScrollTrigger: {
    refresh: vi.fn(),
  },
}));

function stubMediaQueries({
  desktop = true,
  tabletOrLarger = true,
  reducedMotion = false,
}: {
  desktop?: boolean;
  tabletOrLarger?: boolean;
  reducedMotion?: boolean;
} = {}) {
  vi.stubGlobal('matchMedia', vi.fn((query: string) => ({
    matches: query.includes('prefers-reduced-motion')
      ? reducedMotion
      : query.includes('1100')
        ? desktop
        : tabletOrLarger,
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: () => true,
  } as MediaQueryList)));
}

describe('WhyEquiConnected editorial journey', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    stubMediaQueries();
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it('pins the wide journey, advances cards with progress, and reverts on cleanup', async () => {
    const { unmount } = render(<WhyEquiConnected />);

    await waitFor(() => expect(gsapMocks.fromTo).toHaveBeenCalledOnce());
    const stage = document.querySelector<HTMLElement>('[data-why-stage]');
    expect(stage?.getAttribute('data-why-mode')).toBe('pinned');

    const animation = gsapMocks.fromTo.mock.calls[0][2];
    expect(animation.scrollTrigger.pin).toBe(stage);
    expect(animation.scrollTrigger.start).toBe('top top+=112');
    expect(typeof animation.scrollTrigger.end).toBe('function');

    const cards = within(stage as HTMLElement).getAllByRole('article');
    const images = within(stage as HTMLElement).getAllByRole('img');
    expect(images).toHaveLength(4);
    expect(images.map((image) => image.getAttribute('src'))).toEqual([
      '/stable-panel.jpg',
      '/hospital1.png',
      '/provider-veterinary-care.jpg',
      '/about-equiconnected-transparent.png',
    ]);
    act(() => animation.scrollTrigger.onUpdate({ progress: 0.72 }));
    expect(cards[2].getAttribute('data-card-state')).toBe('active');
    expect(within(cards[2]).getByRole('button').getAttribute('aria-pressed')).toBe('true');

    act(() => animation.scrollTrigger.onUpdate({ progress: 1 }));
    expect(cards[3].getAttribute('data-card-state')).toBe('active');

    unmount();
    expect(gsapMocks.revert).toHaveBeenCalledOnce();
  });

  it('keeps natural scrolling and skips GSAP when reduced motion is preferred', async () => {
    stubMediaQueries({ desktop: true, reducedMotion: true });
    render(<WhyEquiConnected />);

    const stage = document.querySelector<HTMLElement>('[data-why-stage]');
    await waitFor(() => expect(stage?.getAttribute('data-why-mode')).toBe('natural'));
    expect(gsapMocks.fromTo).not.toHaveBeenCalled();
    expect(within(stage as HTMLElement).getAllByRole('article')).toHaveLength(4);
  });

  it('keeps scroll-driven progress on tablet without pinning the stage', async () => {
    stubMediaQueries({ desktop: false, tabletOrLarger: true });
    render(<WhyEquiConnected />);

    await waitFor(() => expect(gsapMocks.fromTo).toHaveBeenCalledOnce());
    const stage = document.querySelector<HTMLElement>('[data-why-stage]');
    const animation = gsapMocks.fromTo.mock.calls[0][2];
    expect(stage?.getAttribute('data-why-mode')).toBe('scroll');
    expect(animation.scrollTrigger.pin).toBe(false);
    expect(animation.scrollTrigger.start).toBe('top 78%');
    expect(animation.scrollTrigger.end).toBe('bottom 32%');

    const cards = within(stage as HTMLElement).getAllByRole('article');
    act(() => animation.scrollTrigger.onUpdate({ progress: 0.38 }));
    expect(cards[1].getAttribute('data-card-state')).toBe('active');
  });

  it('uses the natural fallback when matchMedia is unavailable', async () => {
    vi.unstubAllGlobals();
    render(<WhyEquiConnected />);

    const stage = document.querySelector<HTMLElement>('[data-why-stage]');
    await waitFor(() => expect(stage?.getAttribute('data-why-mode')).toBe('natural'));
    expect(gsapMocks.registerPlugin).not.toHaveBeenCalled();
    expect(gsapMocks.fromTo).not.toHaveBeenCalled();
  });
});
