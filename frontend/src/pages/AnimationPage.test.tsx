import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { useEffect } from 'react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { AnimationPage } from './AnimationPage';

const sceneMock = vi.hoisted(() => ({ status: 'ready' as 'loading' | 'ready' | 'complete' | 'unsupported' }));

vi.mock('@/components/animation/HorseScene', () => ({
  HorseScene: ({
    playToken,
    onStatusChange,
  }: {
    playToken: number;
    onStatusChange: (status: 'loading' | 'ready' | 'complete' | 'unsupported') => void;
  }) => {
    useEffect(() => {
      onStatusChange(sceneMock.status);
    }, [onStatusChange]);
    return <div data-testid="horse-scene" data-play-token={playToken} />;
  },
}));

afterEach(() => {
  cleanup();
  sceneMock.status = 'ready';
});

function renderPage() {
  return render(
    <MemoryRouter>
      <AnimationPage />
    </MemoryRouter>
  );
}

describe('AnimationPage', () => {
  it('presents an isolated public scene with an accessible play contract', async () => {
    const user = userEvent.setup();
    renderPage();

    expect(screen.getByRole('heading', { name: /From quiet strength.*open ground/ })).toBeTruthy();
    expect(screen.getByRole('status')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Play horse transformation' })).toBeTruthy();

    await user.click(screen.getByRole('button', { name: 'Play horse transformation' }));
    expect(screen.getByTestId('horse-scene').getAttribute('data-play-token')).toBe('1');
  });

  it('shows a usable fallback when WebGL is unavailable', async () => {
    sceneMock.status = 'unsupported';
    renderPage();

    await waitFor(() => {
      expect(screen.getByRole('alert').textContent).toContain('modern browser with WebGL');
    });
    expect(screen.getByRole('button', { name: 'Play horse transformation' })).toHaveProperty('disabled', true);
  });

  it('keeps Play disabled until the scene and local model finish loading', async () => {
    sceneMock.status = 'loading';
    renderPage();

    expect(await screen.findByRole('button', { name: 'Play horse transformation' }))
      .toHaveProperty('disabled', true);
    expect(screen.getByRole('status').textContent).toContain('Preparing the water and horse');
  });

  it('exposes Replay and resets the scene token after completion', async () => {
    const user = userEvent.setup();
    sceneMock.status = 'complete';
    renderPage();

    const replay = await screen.findByRole('button', { name: 'Replay horse transformation' });
    await user.click(replay);
    expect(screen.getByTestId('horse-scene').getAttribute('data-play-token')).toBe('1');
  });
});