import { act, cleanup, render, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { HowItWorksScroll } from './HowItWorksScroll';

const gsapMocks = vi.hoisted(() => {
  const revert = vi.fn();
  return {
    registerPlugin: vi.fn(),
    revert,
    context: vi.fn((callback: () => void) => {
      callback();
      return { revert };
    }),
    to: vi.fn(),
  };
});

vi.mock('gsap', () => ({
  default: {
    registerPlugin: gsapMocks.registerPlugin,
    context: gsapMocks.context,
    to: gsapMocks.to,
  },
}));

vi.mock('gsap/ScrollTrigger', () => ({
  ScrollTrigger: {},
}));

describe('HowItWorksScroll responsive animation lifecycle', () => {
  let desktopMatches = false;
  let desktopListeners: Set<(event: MediaQueryListEvent) => void>;

  beforeEach(() => {
    desktopMatches = false;
    desktopListeners = new Set();
    vi.clearAllMocks();

    vi.spyOn(HTMLElement.prototype, 'offsetHeight', 'get').mockImplementation(function getOffsetHeight(
      this: HTMLElement,
    ) {
      if (this.hasAttribute('data-care-journey-track')) return 1800;
      if (this.hasAttribute('data-care-journey-viewport')) return 600;
      return 0;
    });
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: 768 });
    vi.stubGlobal('matchMedia', vi.fn((query: string) => {
      const isMotionQuery = query.includes('prefers-reduced-motion');
      const listeners = isMotionQuery ? new Set<(event: MediaQueryListEvent) => void>() : desktopListeners;
      return {
        get matches() {
          return isMotionQuery ? false : desktopMatches;
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

  it('initializes the horizontal tween when a narrow layout becomes desktop', async () => {
    render(<HowItWorksScroll />);
    expect(gsapMocks.to).not.toHaveBeenCalled();

    desktopMatches = true;
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: 1200 });
    act(() => {
      desktopListeners.forEach((listener) => listener({ matches: true } as MediaQueryListEvent));
    });

    await waitFor(() => expect(gsapMocks.to).toHaveBeenCalledOnce());
  });

  it('reverts the horizontal tween when a desktop layout becomes narrow', async () => {
    desktopMatches = true;
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: 1200 });
    render(<HowItWorksScroll />);
    await waitFor(() => expect(gsapMocks.to).toHaveBeenCalledOnce());

    desktopMatches = false;
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: 768 });
    act(() => {
      desktopListeners.forEach((listener) => listener({ matches: false } as MediaQueryListEvent));
    });

    await waitFor(() => expect(gsapMocks.revert).toHaveBeenCalledOnce());
  });
});