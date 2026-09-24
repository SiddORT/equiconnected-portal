import { useEffect, useRef, type ReactNode } from 'react';
import { Card } from '@/components/ui/Card';
import styles from './ProviderWizard.module.css';

interface Step {
  title: string;
  description: string;
}

export interface ReviewSection {
  title: string;
  step: number;
  items: { label: string; value: ReactNode }[];
}

export function ProviderWizardHeader({
  steps,
  current,
  onSelect,
  locked = false,
  mode = 'add',
}: {
  steps: Step[];
  current: number;
  onSelect: (step: number) => void;
  locked?: boolean;
  mode?: 'add' | 'edit';
}) {
  const heading = useRef<HTMLHeadingElement>(null);
  const activeStep = useRef<HTMLLIElement>(null);
  useEffect(() => {
    heading.current?.focus();
    activeStep.current?.scrollIntoView?.({ block: 'nearest', inline: 'nearest' });
  }, [current]);

  return (
    <div className={styles.header}>
      <div className={styles.intro}>
        <div>
          <p className={styles.eyebrow}>{mode === 'edit' ? 'EDIT PROVIDER' : 'ADD PROVIDER'} · STEP {current + 1} OF {steps.length}</p>
          <h2 className={styles.title} ref={heading} tabIndex={-1}>{steps[current].title}</h2>
          <p className={styles.description}>{steps[current].description}</p>
        </div>
        <span className={styles.count}>{current === steps.length - 1 ? 'Final check' : `${steps.length - current - 1} steps remaining`}</span>
      </div>
      <nav aria-label="Provider setup steps" className={styles.nav}>
        <ol className={styles.steps}>
          {steps.map((step, index) => (
            <li key={step.title} ref={current === index ? activeStep : undefined} className={`${styles.step} ${current === index ? styles.active : ''} ${index < current ? styles.done : ''}`}>
              {index < current ? (
                <button type="button" disabled={locked} onClick={() => onSelect(index)} aria-label={`Return to ${step.title}`}>
                  <span className={styles.number} aria-hidden="true">✓</span>
                  <span className={styles.stepLabel}>{step.title}</span>
                </button>
              ) : (
                <span aria-current={index === current ? 'step' : undefined}>
                  <span className={styles.number} aria-hidden="true">{index + 1}</span>
                  <span className={styles.stepLabel}>{step.title}</span>
                </span>
              )}
            </li>
          ))}
        </ol>
      </nav>
    </div>
  );
}

export function ProviderWizardReview({
  sections,
  onEdit,
  locked = false,
}: {
  sections: ReviewSection[];
  onEdit: (step: number) => void;
  locked?: boolean;
}) {
  return (
    <div className={styles.review}>
      {sections.map((section) => (
        <Card key={section.title} padding="lg" shadow="sm">
          <div className={styles.reviewHeader}>
            <h3>{section.title}</h3>
            <button type="button" disabled={locked} onClick={() => onEdit(section.step)} aria-label={`Edit ${section.title}`}>Edit</button>
          </div>
          <dl className={styles.reviewDetails}>
            {section.items.map((item) => (
              <div key={item.label}>
                <dt>{item.label}</dt>
                <dd>{item.value || '—'}</dd>
              </div>
            ))}
          </dl>
        </Card>
      ))}
    </div>
  );
}