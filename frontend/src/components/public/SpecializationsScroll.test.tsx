import { act, cleanup, render, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { SpecializationsScroll } from './SpecializationsScroll';

const gsapMocks = vi.hoisted(() => {
  const revert = vi.fn();
  return {
    registerPlugin: vi.fn(),
    revert,
    context: vi.fn((callback: () => void) => {
      callback();
      return { revert };
    }),
    to: vi.fn((_target: unknown, _vars: unknown) => ({ animation: 'horizontal-track' })),
    fromTo: vi.fn(),
  };
});

const scrollTriggerMocks = vi.hoisted(() => ({
  refresh: vi.fn(),
}));

vi.mock('gsap', () => ({
  default: {
    registerPlugin: gsapMocks.registerPlugin,
    context: gsapMocks.context,
    to: gsapMocks.to,
    fromTo: gsapMocks.fromTo,
  },
}));

vi.mock('gsap/ScrollTrigger', () => ({
  ScrollTrigger: {
    refresh: scrollTriggerMocks.refresh,
  },
}));

describe('SpecializationsScroll animation lifecycle', () => {
  let desktopMatches = true;
  let motionMatches = false;
  let desktopListeners: Set<(event: MediaQueryListEvent) => void>;
  let motionListeners: Set<(event: MediaQueryListEvent) => void>;

  beforeEach(() => {
    desktopMatches = true;
    motionMatches = false;
    desktopListeners = new Set();
    motionListeners = new Set();
    vi.clearAllMocks();
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: 1280 });

    vi.spyOn(HTMLElement.prototype, 'scrollWidth', 'get').mockImplementation(function getScrollWidth(
      this: HTMLElement,
    ) {
      return this.hasAttribute('data-specialization-track') ? 1600 : 0;
    });
    vi.spyOn(HTMLElement.prototype, 'clientWidth', 'get').mockImplementation(function getClientWidth(
      this: HTMLElement,
    ) {
      return this.hasAttribute('data-specialization-viewport') ? 1000 : 0;
    });
    vi.stubGlobal('matchMedia', vi.fn((query: string) => {
      const isMotionQuery = query.includes('prefers-reduced-motion');
      const listeners = isMotionQuery ? motionListeners : desktopListeners;
      return {
        get matches() {
          return isMotionQuery ? motionMatches : desktopMatches;
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

  it('pins only the measured stage and carries the active state through the final card', async () => {
    render(<MemoryRouter><SpecializationsScroll /></MemoryRouter>);

    await waitFor(() => expect(gsapMocks.context).toHaveBeenCalledOnce());
    const stage = document.querySelector<HTMLElement>('[data-specialization-stage]');
    const trackTween = gsapMocks.to.mock.calls[0]?.[1] as {
      x: () => number;
      scrollTrigger: {
        pin: HTMLElement;
        scrub: boolean;
        start: string;
        end: () => string;
        onUpdate: (self: { progress: number }) => void;
      };
    };
    expect(trackTween.x()).toBe(-600);
    expect(trackTween.scrollTrigger.pin).toBe(stage);
    expect(trackTween.scrollTrigger.scrub).toBe(true);
    expect(trackTween.scrollTrigger.start).toBe('top top+=124');
    expect(trackTween.scrollTrigger.end()).toBe('+=800');
    expect(gsapMocks.fromTo).toHaveBeenCalledTimes(4);

    const cards = Array.from(document.querySelectorAll<HTMLElement>('[data-specialization-card]'));
    expect(cards[0].dataset.cardState).toBe('active');
    act(() => trackTween.scrollTrigger.onUpdate({ progress: 1 }));
    expect(cards[cards.length - 1]?.dataset.cardState).toBe('active');
    expect(cards.slice(0, -1).every((card) => card.dataset.cardState === 'passed')).toBe(true);
  });

  it('disables and cleans up desktop pinning for reduced motion and narrow layouts', async () => {
    motionMatches = true;
    const { unmount } = render(<MemoryRouter><SpecializationsScroll /></MemoryRouter>);

    await waitFor(() => {
      expect(document.getElementById('specializations')?.className).toContain('reducedMotion');
    });
    expect(gsapMocks.context).not.toHaveBeenCalled();
    expect(document.querySelector('[data-specialization-stage]')?.getAttribute(
      'data-specialization-mode',
    )).toBe('horizontal');

    unmount();
    expect(desktopListeners.size).toBe(0);
    expect(motionListeners.size).toBe(0);
  });

  it('keeps card interactions live until breakpoint cleanup removes them', async () => {
    render(<MemoryRouter><SpecializationsScroll /></MemoryRouter>);
    await waitFor(() => expect(gsapMocks.context).toHaveBeenCalledOnce());

    const card = document.querySelector<HTMLElement>('[data-specialization-card]');
    card?.dispatchEvent(new Event('pointerenter'));
    expect(gsapMocks.to).toHaveBeenCalledTimes(3);

    desktopMatches = false;
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: 768 });
    act(() => {
      desktopListeners.forEach((listener) => listener({ matches: false } as MediaQueryListEvent));
    });
    await waitFor(() => expect(gsapMocks.revert).toHaveBeenCalledOnce());

    card?.dispatchEvent(new Event('pointerenter'));
    expect(gsapMocks.to).toHaveBeenCalledTimes(3);
  });
});