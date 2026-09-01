import { cleanup, fireEvent, render, within } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { WhyEquiConnected } from './WhyEquiConnected';

describe('WhyEquiConnected editorial journey', () => {
  afterEach(() => {
    cleanup();
  });

  it('renders one natural-flow journey with complete card content', () => {
    render(<WhyEquiConnected />);

    const stage = document.querySelector<HTMLElement>('[data-why-stage]');
    expect(stage?.getAttribute('data-why-mode')).toBe('natural');
    expect(document.querySelector('.pin-spacer')).toBeNull();

    const cards = within(stage as HTMLElement).getAllByRole('article');
    const images = within(stage as HTMLElement).getAllByRole('img');
    expect(images).toHaveLength(4);
    expect(images.map((image) => image.getAttribute('src'))).toEqual([
      '/stable-panel.jpg',
      '/hospital1.png',
      '/provider-veterinary-care.jpg',
      '/about-equiconnected-transparent.png',
    ]);
    expect(cards.every((card) => card.textContent?.includes('Explore'))).toBe(true);
    expect(cards[0].getAttribute('data-card-state')).toBe('active');
  });

  it('activates a card through click without relying on hover or scroll', () => {
    render(<WhyEquiConnected />);

    const stage = document.querySelector<HTMLElement>('[data-why-stage]');
    const cards = within(stage as HTMLElement).getAllByRole('article');
    const buttons = within(stage as HTMLElement).getAllByRole('button');

    fireEvent.click(buttons[2]);

    expect(cards[2].getAttribute('data-card-state')).toBe('active');
    expect(buttons[2].getAttribute('aria-pressed')).toBe('true');
    expect(cards[0].getAttribute('data-card-state')).toBe('passed');
  });

  it('keeps the natural layout when reduced motion is preferred', () => {
    window.matchMedia = () => ({
      matches: true,
      media: '(prefers-reduced-motion: reduce)',
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => true,
    } as MediaQueryList);
    render(<WhyEquiConnected />);

    const stage = document.querySelector<HTMLElement>('[data-why-stage]');
    expect(stage?.getAttribute('data-why-mode')).toBe('natural');
    expect(document.querySelector('[data-why-section]')?.className).toContain('reducedMotion');
  });
});
