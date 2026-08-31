import { act, cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { HorseScene, type SceneStatus, type TimelinePhase } from './HorseScene';

const rendererState = vi.hoisted(() => ({ failConstruction: false }));

vi.mock('three', async (importOriginal) => {
  const actual = await importOriginal<typeof import('three')>();
  return {
    ...actual,
    WebGLRenderer: class {
      constructor() {
        if (rendererState.failConstruction) {
          throw new Error('WebGL context creation failed');
        }
      }
    },
  };
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  rendererState.failConstruction = false;
});

function mockWebGLUnavailable() {
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(null);
}

describe('HorseScene capability fallback', () => {
  it('replaces an unsupported canvas with a visible horse poster', async () => {
    mockWebGLUnavailable();
    const onStatusChange = vi.fn<(status: SceneStatus) => void>();
    const onPhaseChange = vi.fn<(phase: TimelinePhase) => void>();

    render(
      <HorseScene
        playToken={0}
        reducedMotion={false}
        onStatusChange={onStatusChange}
        onPhaseChange={onPhaseChange}
      />
    );

    expect((await screen.findByTestId('horse-fallback')).getAttribute('data-step')).toBe('opening');
    expect(screen.getByAltText(/dark horse standing in an open field/i)).toBeTruthy();
    expect(screen.queryByLabelText('Cinematic horse transformation scene')).toBeNull();
    expect(onStatusChange).toHaveBeenCalledWith('unsupported');
  });

  it('uses the same stable fallback when renderer construction fails', async () => {
    rendererState.failConstruction = true;
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({} as WebGLRenderingContext);
    const onStatusChange = vi.fn<(status: SceneStatus) => void>();
    const onPhaseChange = vi.fn<(phase: TimelinePhase) => void>();

    render(
      <HorseScene
        playToken={0}
        reducedMotion={false}
        onStatusChange={onStatusChange}
        onPhaseChange={onPhaseChange}
      />
    );

    expect(await screen.findByTestId('horse-fallback')).toBeTruthy();
    expect(onStatusChange).toHaveBeenCalledWith('unsupported');
    expect(screen.queryByText(/preparing/i)).toBeNull();
  });

  it('plays and deterministically replays the reduced-motion fallback', async () => {
    mockWebGLUnavailable();
    const onStatusChange = vi.fn<(status: SceneStatus) => void>();
    const onPhaseChange = vi.fn<(phase: TimelinePhase) => void>();
    const view = render(
      <HorseScene
        playToken={0}
        reducedMotion
        onStatusChange={onStatusChange}
        onPhaseChange={onPhaseChange}
      />
    );

    await screen.findByTestId('horse-fallback');
    view.rerender(
      <HorseScene
        playToken={1}
        reducedMotion
        onStatusChange={onStatusChange}
        onPhaseChange={onPhaseChange}
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId('horse-fallback').getAttribute('data-step')).toBe('complete');
    });
    expect(onPhaseChange).toHaveBeenCalledWith('opening');
    expect(onPhaseChange).toHaveBeenCalledWith('complete');
    expect(onStatusChange).toHaveBeenCalledWith('complete');

    const completedCalls = onStatusChange.mock.calls.filter(([status]) => status === 'complete').length;
    view.rerender(
      <HorseScene
        playToken={2}
        reducedMotion
        onStatusChange={onStatusChange}
        onPhaseChange={onPhaseChange}
      />
    );

    await waitFor(() => {
      const replayedCalls = onStatusChange.mock.calls.filter(([status]) => status === 'complete').length;
      expect(replayedCalls).toBe(completedCalls + 1);
    });
    expect(screen.getByTestId('horse-fallback').getAttribute('data-progress')).toBe('1.00');
  });

  it('advances, completes, and resets the normal-motion fallback timeline', async () => {
    mockWebGLUnavailable();
    let nextFrameId = 0;
    const frames = new Map<number, FrameRequestCallback>();
    vi.spyOn(performance, 'now').mockReturnValue(100);
    vi.spyOn(window, 'requestAnimationFrame').mockImplementation((callback) => {
      const frameId = ++nextFrameId;
      frames.set(frameId, callback);
      return frameId;
    });
    vi.spyOn(window, 'cancelAnimationFrame').mockImplementation((frameId) => {
      frames.delete(frameId);
    });
    const runNextFrame = (timestamp: number) => {
      const [frameId, callback] = frames.entries().next().value as [number, FrameRequestCallback];
      frames.delete(frameId);
      callback(timestamp);
    };
    const onStatusChange = vi.fn<(status: SceneStatus) => void>();
    const onPhaseChange = vi.fn<(phase: TimelinePhase) => void>();
    const view = render(
      <HorseScene
        playToken={0}
        reducedMotion={false}
        onStatusChange={onStatusChange}
        onPhaseChange={onPhaseChange}
      />
    );

    await screen.findByTestId('horse-fallback');
    view.rerender(
      <HorseScene
        playToken={1}
        reducedMotion={false}
        onStatusChange={onStatusChange}
        onPhaseChange={onPhaseChange}
      />
    );
    expect(onStatusChange).toHaveBeenCalledWith('playing');

    act(() => runNextFrame(2800));
    expect(screen.getByTestId('horse-fallback').getAttribute('data-step')).toBe('transforming');
    act(() => runNextFrame(5400));
    expect(screen.getByTestId('horse-fallback').getAttribute('data-step')).toBe('complete');
    expect(onStatusChange).toHaveBeenCalledWith('complete');

    view.rerender(
      <HorseScene
        playToken={2}
        reducedMotion={false}
        onStatusChange={onStatusChange}
        onPhaseChange={onPhaseChange}
      />
    );
    expect(screen.getByTestId('horse-fallback').getAttribute('data-step')).toBe('opening');
    expect(screen.getByTestId('horse-fallback').getAttribute('data-progress')).toBe('0.00');
  });
});