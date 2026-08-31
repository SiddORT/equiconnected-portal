import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  HorseScene,
  type SceneStatus,
  type TimelinePhase,
} from '@/components/animation/HorseScene';
import styles from './AnimationPage.module.css';

const PHASE_COPY: Record<TimelinePhase, string> = {
  opening: 'A young pony steps through the shallows',
  gathering: 'The water gathers around each hoof',
  transforming: 'Strength rises through the current',
  burst: 'The transformation breaks the surface',
  pause: 'A new presence holds the horizon',
  gallop: 'The adult horse finds its stride',
  pullback: 'The view opens onto the whole scene',
  complete: 'The journey is complete',
};

function useReducedMotion() {
  const [reducedMotion, setReducedMotion] = useState(false);

  useEffect(() => {
    const query = window.matchMedia?.('(prefers-reduced-motion: reduce)');
    if (!query) return;
    const update = () => setReducedMotion(query.matches);
    update();
    query.addEventListener?.('change', update);
    return () => query.removeEventListener?.('change', update);
  }, []);

  return reducedMotion;
}

export function AnimationPage() {
  const [sceneStatus, setSceneStatus] = useState<SceneStatus>('loading');
  const [phase, setPhase] = useState<TimelinePhase>('opening');
  const [playToken, setPlayToken] = useState(0);
  const reducedMotion = useReducedMotion();

  const handleStatusChange = useCallback((status: SceneStatus) => {
    setSceneStatus(status);
  }, []);

  const canPlay = sceneStatus === 'ready' || sceneStatus === 'complete';
  const isRunning = sceneStatus === 'playing';
  const isComplete = sceneStatus === 'complete' || phase === 'complete';
  const statusText =
    sceneStatus === 'loading' ? 'Preparing the water and horse…' :
    sceneStatus === 'unsupported' ? 'WebGL is unavailable in this browser.' :
    sceneStatus === 'error' ? 'The scene could not be initialized.' :
    isComplete ? PHASE_COPY.complete :
    PHASE_COPY[phase];

  function handlePlay() {
    if (!canPlay || isRunning) return;
    setPlayToken((token) => token + 1);
  }

  return (
    <div className={styles.page}>
      <div className={styles.atmosphere} aria-hidden="true" />
      <header className={styles.header}>
        <Link to="/" className={styles.brand} aria-label="Return to EquiConnected home">
          <span className={styles.brandMark} aria-hidden="true">EC</span>
          <span>equiconnected</span>
        </Link>
        <span className={styles.headerLabel}>A study in motion</span>
      </header>

      <main className={styles.main} id="main-content">
        <section className={styles.intro} aria-labelledby="animation-heading">
          <p className={styles.eyebrow}><span />The water remembers</p>
          <h1 id="animation-heading">From quiet strength<br /><em>to open ground.</em></h1>
          <p className={styles.lede}>
            Watch a small step become a full stride. A cinematic study of growth,
            movement, and the animal waiting inside the current.
          </p>
        </section>

        <section className={styles.stage} aria-label="Cinematic horse transformation">
          <HorseScene
            playToken={playToken}
            reducedMotion={reducedMotion}
            onStatusChange={handleStatusChange}
            onPhaseChange={setPhase}
          />
          <div className={styles.stageVignette} aria-hidden="true" />
          <div className={styles.stageCaption}>
            <span className={styles.captionKicker}>Equine study / 01</span>
            <span className={styles.captionRule} />
            <span>Shallow water, first light</span>
          </div>
          <div className={styles.progress} aria-hidden="true">
            <span style={{ width: `${isComplete ? 100 : sceneStatus === 'loading' ? 12 : phase === 'opening' ? 16 : phase === 'gathering' ? 30 : phase === 'transforming' ? 52 : phase === 'burst' ? 64 : phase === 'pause' ? 72 : phase === 'gallop' ? 84 : 94}%` }} />
          </div>
          <div className={styles.controls}>
            <div className={styles.statusBlock}>
              <span className={styles.statusDot} data-active={isRunning || sceneStatus === 'loading'} aria-hidden="true" />
              <div>
                <p className={styles.statusLabel}>Sequence status</p>
                <p className={styles.statusText} role="status" aria-live="polite">{statusText}</p>
              </div>
            </div>
            <button
              type="button"
              className={styles.playButton}
              onClick={handlePlay}
              disabled={!canPlay || isRunning}
              aria-label={isComplete ? 'Replay horse transformation' : 'Play horse transformation'}
            >
              <span aria-hidden="true">{isComplete ? '↻' : '▶'}</span>
              {isComplete ? 'Replay' : 'Play sequence'}
            </button>
          </div>
        </section>

        {(sceneStatus === 'unsupported' || sceneStatus === 'error') && (
          <div className={styles.fallback} role="alert">
            <strong>This experience needs a modern browser with WebGL.</strong>
            <p>
              The animation cannot run here, but the EquiConnected experience is still available.
              Try a current version of Chrome, Safari, Firefox, or Edge.
            </p>
          </div>
        )}

        <p className={styles.motionNote}>
          {reducedMotion ? 'Reduced motion is on — the sequence uses a shorter, gentler reveal.' : 'Move freely. The scene is designed to be replayed.'}
        </p>
      </main>

      <footer className={styles.footer}>
        <span>EquiConnected</span>
        <span>© {new Date().getFullYear()}</span>
        <Link to="/">Back to home</Link>
      </footer>
    </div>
  );
}