import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { ProviderPhotoComparison } from './ProviderPhotoComparison';

afterEach(cleanup);

const original = {
  storage_reference: '/uploads/providers/provider-1/photos/exterior.png',
  caption: 'Original exterior',
  alt_text: 'The approved exterior',
  display_order: 0,
  is_thumbnail: true,
};

describe('ProviderPhotoComparison', () => {
  it('shows actual current and proposed images with additions, removals and all metadata changes', () => {
    render(<ProviderPhotoComparison
      current={[original, { ...original, storage_reference: '/uploads/providers/provider-1/photos/removed.png', alt_text: 'Removed waiting area', is_thumbnail: false, display_order: 1 }]}
      proposed={[
        { ...original, storage_reference: '/uploads/providers/provider-1/photos/new.png', caption: 'New treatment room', alt_text: 'A treatment room' },
        { ...original, caption: 'Updated exterior', alt_text: 'Accessible new description', display_order: 1, is_thumbnail: false },
      ]}
    />);
    const comparison = screen.getByRole('region', { name: 'Photo comparison' });
    const current = within(comparison).getByRole('region', { name: 'Current photos' });
    const proposed = within(comparison).getByRole('region', { name: 'Proposed photos' });
    expect(within(current).getByRole('img', { name: original.alt_text }).getAttribute('src')).toBe(original.storage_reference);
    expect(within(current).getByText('Removed')).toBeTruthy();
    expect(within(proposed).getByText('Added')).toBeTruthy();
    expect(within(proposed).getByText('Changed · Metadata changed · Order changed · Profile photo changed')).toBeTruthy();
    expect(within(proposed).getByText('New treatment room')).toBeTruthy();
    expect(within(proposed).getByText('Alt text: Accessible new description')).toBeTruthy();
    expect(within(proposed).getByText('Photo 2 · order 1')).toBeTruthy();
    expect(within(proposed).getAllByText('Profile photo')).toHaveLength(1);
    expect(comparison.textContent).not.toContain('storage_reference');
  });

  it('retains caption and alt text when a preview fails', () => {
    render(<ProviderPhotoComparison current={[]} proposed={[original]} />);
    fireEvent.error(screen.getByRole('img', { name: original.alt_text }));
    expect(screen.getByText('Image could not be loaded')).toBeTruthy();
    expect(screen.getByRole('img', { name: `${original.alt_text}: image failed to load` })).toBeTruthy();
    expect(screen.getByText(original.caption)).toBeTruthy();
    expect(screen.getByText(`Alt text: ${original.alt_text}`)).toBeTruthy();
    expect(screen.getByText('Profile photo')).toBeTruthy();
  });

  it('shows explicit empty states and missing metadata', () => {
    const { rerender } = render(<ProviderPhotoComparison current={[]} proposed={[]} />);
    expect(screen.getAllByText('No photos in this profile.')).toHaveLength(2);
    rerender(<ProviderPhotoComparison current={[]} proposed={[{ storage_reference: original.storage_reference }]} />);
    expect(screen.getByText('No caption')).toBeTruthy();
    expect(screen.getByText('Alt text: Not provided')).toBeTruthy();
  });

  it.each(['javascript:alert(1)', '//untrusted.example/image.png', 'data:image/svg+xml,<svg/>', '/uploads/../private.png', '/uploads/\\private.png'])(
    'does not request unsafe reference %s',
    (reference) => {
      const { container } = render(<ProviderPhotoComparison current={[]} proposed={[{ ...original, storage_reference: reference }]} />);
      expect(container.querySelector('img')).toBeNull();
      expect(screen.getByText('Image unavailable')).toBeTruthy();
    },
  );

  it('supports legacy approved HTTPS images and sorts cards by display order', () => {
    const photo = { ...original, storage_reference: 'https://example.test/legacy.png' };
    render(<ProviderPhotoComparison current={[{ ...photo, display_order: 5 }, { ...original, display_order: 1 }]} proposed={[photo]} />);
    const current = screen.getByRole('region', { name: 'Current photos' });
    expect(within(current).getAllByRole('img')[0].getAttribute('src')).toBe(original.storage_reference);
    expect(within(current).getAllByRole('img')[1].getAttribute('src')).toBe(photo.storage_reference);
  });

  it('matches duplicate storage references individually, rather than hiding an added copy', () => {
    render(<ProviderPhotoComparison current={[original]} proposed={[original, original]} />);
    const proposed = screen.getByRole('region', { name: 'Proposed photos' });
    expect(within(proposed).getByText('Unchanged')).toBeTruthy();
    expect(within(proposed).getByText('Added')).toBeTruthy();
  });
});