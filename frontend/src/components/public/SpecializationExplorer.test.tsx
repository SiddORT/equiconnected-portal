import { act, cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { SpecializationExplorer } from './SpecializationExplorer';

const gsapMocks = vi.hoisted(() => {
  const holder: {
    animation: Record<string, unknown> | null;
    tween: { scrollTrigger: { start: number; end: number } };
  } = {
    animation: null,
    tween: { scrollTrigger: { start: 112, end: 1512 } },
  };
  const revert = vi.fn();
  return {
    holder,
    registerPlugin: vi.fn(),
    revert,
    set: vi.fn(),
    context: vi.fn((callback: () => void) => {
      callback();
      return { revert };
    }),
    to: vi.fn((_target: unknown, animation: Record<string, unknown>) => {
      holder.animation = animation;
      return holder.tween;
    }),
  };
});

vi.mock('gsap', () => ({
  default: {
    registerPlugin: gsapMocks.registerPlugin,
    context: gsapMocks.context,
    set: gsapMocks.set,
    to: gsapMocks.to,
  },
}));

vi.mock('gsap/ScrollTrigger', () => ({
  ScrollTrigger: {},
}));

describe('SpecializationExplorer premium scroll', () => {
  let desktopMatches = true;
  let reducedMotionMatches = false;
  let desktopListeners: Set<(event: MediaQueryListEvent) => void>;
  let motionListeners: Set<(event: MediaQueryListEvent) => void>;

  beforeEach(() => {
    desktopMatches = true;
    reducedMotionMatches = false;
    desktopListeners = new Set();
    motionListeners = new Set();
    gsapMocks.holder.animation = null;
    gsapMocks.holder.tween.scrollTrigger.start = 112;
    gsapMocks.holder.tween.scrollTrigger.end = 1512;
    vi.clearAllMocks();

    vi.spyOn(HTMLElement.prototype, 'scrollWidth', 'get').mockImplementation(function getScrollWidth(
      this: HTMLElement,
    ) {
      return this.hasAttribute('data-premium-track') ? 2400 : 0;
    });
    vi.spyOn(HTMLElement.prototype, 'clientWidth', 'get').mockImplementation(function getClientWidth(
      this: HTMLElement,
    ) {
      return this.hasAttribute('data-premium-viewport') ? 1000 : 0;
    });
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: 1280 });
    vi.stubGlobal('scrollTo', vi.fn());
    vi.stubGlobal('matchMedia', vi.fn((query: string) => {
      const isMotionQuery = query.includes('prefers-reduced-motion');
      const listeners = isMotionQuery ? motionListeners : desktopListeners;
      return {
        get matches() {
          return isMotionQuery ? reducedMotionMatches : desktopMatches;
        },
        media: query,
        onchange: null,
        addEventListener: (_type: string, listener: (event: MediaQueryListEvent) => void) => {
          listeners.add(listener);
        },
        removeEventListener: (_type: string, listener: (event: MediaQueryListEvent) => void) => {
          listeners.delete(listener);
        },
        addListener: (listener: (event: MediaQueryListEvent) => void) => listeners.add(listener),
        removeListener: (listener: (event: MediaQueryListEvent) => void) => listeners.delete(listener),
        dispatchEvent: () => true,
      } as MediaQueryList;
    }));
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it('removes redundant carousel labels while keeping controls and cards available', () => {
    render(<SpecializationExplorer />);

    expect(screen.queryByText('Find the right perspective')).toBeNull();
    expect(screen.queryByText('Explore specializations')).toBeNull();
    expect(screen.getByRole('button', { name: 'Previous specialization' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Next specialization' })).toBeTruthy();
    expect(document.querySelectorAll('[data-specialization-card]')).toHaveLength(8);
    expect(screen.getByText('Selected Cardiology')).toBeTruthy();
  });

  it('measures full desktop travel, updates progress states, and resets on reduced motion', async () => {
    render(<SpecializationExplorer />);

    await waitFor(() => expect(gsapMocks.to).toHaveBeenCalledOnce());
    const animation = gsapMocks.holder.animation as {
      x: () => number;
      scrollTrigger: {
        pin: boolean;
        end: () => string;
        onUpdate: (self: { progress: number }) => void;
      };
    };
    expect(animation.x()).toBe(-1400);
    expect(animation.scrollTrigger.pin).toBe(true);
    expect(animation.scrollTrigger.end()).toBe('+=1400');

    const cards = Array.from(document.querySelectorAll<HTMLElement>('[data-premium-card]'));
    act(() => animation.scrollTrigger.onUpdate({ progress: 1 }));
    expect(cards.slice(0, -1).every((card) => card.dataset.premiumState === 'passed')).toBe(true);
    expect(cards[cards.length - 1]?.dataset.premiumState).toBe('active');

    screen.getByRole('link', { name: 'Explore Reproduction care options' }).focus();
    expect(window.scrollTo).toHaveBeenCalledWith({ top: 1512, behavior: 'auto' });

    reducedMotionMatches = true;
    act(() => {
      motionListeners.forEach((listener) => listener({ matches: true } as MediaQueryListEvent));
    });

    await waitFor(() => {
      expect(screen.getByRole('region', { name: 'Care, in focus.' })
        .getAttribute('data-premium-motion')).toBe('reduced');
    });
    expect(gsapMocks.revert).toHaveBeenCalledOnce();
    expect(cards[0]?.dataset.premiumState).toBe('active');
    expect(cards.slice(1).every((card) => card.dataset.premiumState === 'upcoming')).toBe(true);
    expect(document.querySelector('[data-premium-stage]')
      ?.getAttribute('data-premium-pinning')).toBe('disabled');
  });

  it('cleans up desktop pinning when the layout becomes narrow', async () => {
    render(<SpecializationExplorer />);

    await waitFor(() => expect(gsapMocks.to).toHaveBeenCalledOnce());
    desktopMatches = false;
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: 768 });
    act(() => {
      desktopListeners.forEach((listener) => listener({ matches: false } as MediaQueryListEvent));
    });

    await waitFor(() => {
      expect(document.querySelector('[data-premium-stage]')
        ?.getAttribute('data-premium-pinning')).toBe('disabled');
    });
    expect(gsapMocks.revert).toHaveBeenCalledOnce();
    const cards = Array.from(document.querySelectorAll<HTMLElement>('[data-premium-card]'));
    expect(cards).toHaveLength(8);
    expect(cards[0]?.dataset.premiumState).toBe('active');
    expect(cards.slice(1).every((card) => card.dataset.premiumState === 'upcoming')).toBe(true);
  });
});