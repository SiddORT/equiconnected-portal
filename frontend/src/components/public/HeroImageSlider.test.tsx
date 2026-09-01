import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { HeroImageSlider } from './HeroImageSlider';

type MotionQuery = MediaQueryList & {
  setMatches: (matches: boolean) => void;
};

function stubMotionPreference(initialMatches: boolean): MotionQuery {
  let matches = initialMatches;
  const listeners = new Set<(event: MediaQueryListEvent) => void>();
  const query = {
    get matches() {
      return matches;
    },
    media: '(prefers-reduced-motion: reduce)',
    onchange: null,
    addEventListener: (_type: string, listener: (event: MediaQueryListEvent) => void) => {
      listeners.add(listener);
    },
    removeEventListener: (_type: string, listener: (event: MediaQueryListEvent) => void) => {
      listeners.delete(listener);
    },
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => true,
    setMatches(nextMatches: boolean) {
      matches = nextMatches;
      const event = { matches, media: this.media } as MediaQueryListEvent;
      listeners.forEach((listener) => listener(event));
    },
  } as MotionQuery;

  vi.stubGlobal('matchMedia', vi.fn(() => query));
  return query;
}

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe('HeroImageSlider', () => {
  it('automatically advances slides on a consistent interval', () => {
    vi.useFakeTimers();
    render(<HeroImageSlider />);
    const slider = screen.getByRole('region', { name: 'Equine care stories' });

    expect(within(slider).getByRole('img', {
      name: 'Dark horse standing in a quiet mountain pasture at sunset',
    })).toBeTruthy();

    act(() => vi.advanceTimersByTime(5599));
    expect(within(slider).getByRole('img', {
      name: 'Dark horse standing in a quiet mountain pasture at sunset',
    })).toBeTruthy();

    act(() => vi.advanceTimersByTime(1));
    expect(within(slider).getByRole('img', {
      name: 'Equine care professional working with a horse indoors',
    })).toBeTruthy();

    act(() => vi.advanceTimersByTime(5600));
    expect(within(slider).getByRole('img', {
      name: 'Warm, well-kept stable with open doors to the paddock',
    })).toBeTruthy();
  });

  it('pauses for hover and focus, then resumes when both have ended', () => {
    vi.useFakeTimers();
    render(<HeroImageSlider />);
    const slider = screen.getByRole('region', { name: 'Equine care stories' });
    const nextButton = within(slider).getByRole('button', { name: 'Next image' });

    fireEvent.mouseEnter(slider);
    act(() => vi.advanceTimersByTime(5600));
    expect(within(slider).getByRole('img', {
      name: 'Dark horse standing in a quiet mountain pasture at sunset',
    })).toBeTruthy();

    fireEvent.mouseLeave(slider);
    act(() => vi.advanceTimersByTime(5600));
    expect(within(slider).getByRole('img', {
      name: 'Equine care professional working with a horse indoors',
    })).toBeTruthy();

    fireEvent.focus(nextButton);
    fireEvent.mouseEnter(slider);
    fireEvent.mouseLeave(slider);
    act(() => vi.advanceTimersByTime(5600));
    expect(within(slider).getByRole('img', {
      name: 'Equine care professional working with a horse indoors',
    })).toBeTruthy();

    fireEvent.blur(nextButton, { relatedTarget: null });
    act(() => vi.advanceTimersByTime(5600));
    expect(within(slider).getByRole('img', {
      name: 'Warm, well-kept stable with open doors to the paddock',
    })).toBeTruthy();
  });

  it('does not autoplay with reduced motion, but responds to preference changes', () => {
    vi.useFakeTimers();
    const motionQuery = stubMotionPreference(true);
    render(<HeroImageSlider />);
    const slider = screen.getByRole('region', { name: 'Equine care stories' });

    act(() => vi.advanceTimersByTime(11200));
    expect(within(slider).getByRole('img', {
      name: 'Dark horse standing in a quiet mountain pasture at sunset',
    })).toBeTruthy();

    act(() => motionQuery.setMatches(false));
    act(() => vi.advanceTimersByTime(5600));
    expect(within(slider).getByRole('img', {
      name: 'Equine care professional working with a horse indoors',
    })).toBeTruthy();
  });

  it('keeps manual controls, indicators, and accessible slide state synchronized', () => {
    render(<HeroImageSlider />);
    const slider = screen.getByRole('region', { name: 'Equine care stories' });
    const nextButton = within(slider).getByRole('button', { name: 'Next image' });
    const previousButton = within(slider).getByRole('button', { name: 'Previous image' });
    const secondIndicator = within(slider).getByRole('button', {
      name: 'Show image 2: Expertise, connected',
    });
    const images = Array.from(slider.querySelectorAll('img'));

    expect(images).toHaveLength(3);
    expect(images[0].getAttribute('aria-hidden')).toBe('false');
    expect(images[1].getAttribute('aria-hidden')).toBe('true');
    expect(images[2].getAttribute('aria-hidden')).toBe('true');
    expect(within(slider).getByText('A considered approach to care')).toBeTruthy();

    fireEvent.click(nextButton);
    expect(within(slider).getByRole('img', {
      name: 'Equine care professional working with a horse indoors',
    })).toBeTruthy();
    expect(secondIndicator.getAttribute('aria-pressed')).toBe('true');
    expect(images[0].getAttribute('alt')).toBe('');
    expect(images[1].getAttribute('aria-hidden')).toBe('false');
    expect(within(slider).getByText('Expertise, connected')).toBeTruthy();

    fireEvent.click(previousButton);
    expect(within(slider).getByRole('img', {
      name: 'Dark horse standing in a quiet mountain pasture at sunset',
    })).toBeTruthy();

    fireEvent.click(within(slider).getByRole('button', {
      name: 'Show image 3: A trusted care community',
    }));
    expect(within(slider).getByRole('img', {
      name: 'Warm, well-kept stable with open doors to the paddock',
    })).toBeTruthy();
  });

  it('cleans up the autoplay timer when unmounted', () => {
    vi.useFakeTimers();
    const { unmount } = render(<HeroImageSlider />);

    expect(vi.getTimerCount()).toBe(1);
    unmount();
    expect(vi.getTimerCount()).toBe(0);
  });
});