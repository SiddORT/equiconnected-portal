import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { adminTopics } from './manual/adminTopics';
import { analyticsTopics } from './manual/analyticsTopics';
import { gettingStartedTopics, memberTopics, providerTopics, troubleshootingTopics } from './manual/roleTopics';
import { manualScreenshots } from './manual/screenshots';
import type { ManualTopic } from './manual/types';
import styles from './UserManualPage.module.css';

const SECTIONS: { title: string; topics: ManualTopic[] }[] = [
  { title: 'Getting started', topics: gettingStartedTopics },
  { title: 'Admin portal', topics: adminTopics },
  { title: 'Provider portal', topics: providerTopics },
  { title: 'Member portal', topics: memberTopics },
  { title: 'Dashboard & Analytics', topics: analyticsTopics },
  { title: 'Troubleshooting', topics: troubleshootingTopics },
];

function topicText(topic: ManualTopic, images: ManualTopic['images'] = []) {
  return [
    topic.title, topic.purpose, topic.where, topic.who,
    ...topic.prerequisites, ...topic.steps, topic.result, ...topic.restrictions,
    ...(images ?? []).flatMap((image) => [image.alt, image.caption]),
  ].join(' ').toLocaleLowerCase();
}

export function UserManualPage() {
  const [search, setSearch] = useState('');
  const [selectedImage, setSelectedImage] = useState<{ src: string; alt: string; caption: string } | null>(null);
  const [showImageFullSize, setShowImageFullSize] = useState(false);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const lastImageButton = useRef<HTMLButtonElement | null>(null);
  const location = useLocation();
  const query = search.trim().toLocaleLowerCase();
  const sections = useMemo(() => SECTIONS.map((section) => ({
    ...section,
    topics: section.topics.map((topic) => ({
      ...topic,
      images: [...(topic.images ?? []), ...(manualScreenshots[topic.id] ?? [])],
    })).filter((topic) => !query || topicText(topic, topic.images).includes(query)),
  })), [query]);

  useEffect(() => {
    if (!location.hash) return;
    setSearch('');
    let anchor = location.hash.slice(1);
    try {
      anchor = decodeURIComponent(anchor);
    } catch {
      // A malformed percent-escape is not a usable anchor; keep the raw hash harmlessly.
    }
    const timer = window.setTimeout(() => {
      const target = document.getElementById(anchor);
      if (target && typeof target.scrollIntoView === 'function') target.scrollIntoView();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [location.hash]);

  useEffect(() => {
    if (!selectedImage || !dialogRef.current) return;
    const dialog = dialogRef.current;
    function handleEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        event.preventDefault();
        setSelectedImage(null);
        requestAnimationFrame(() => lastImageButton.current?.focus());
      }
    }
    if (typeof dialog.showModal === 'function') dialog.showModal();
    else dialog.setAttribute('open', '');
    document.addEventListener('keydown', handleEscape);
    return () => {
      document.removeEventListener('keydown', handleEscape);
      if (dialog.open) {
        if (typeof dialog.close === 'function') dialog.close();
        else dialog.removeAttribute('open');
      }
    };
  }, [selectedImage]);

  function closeImage() {
    setSelectedImage(null);
    setShowImageFullSize(false);
    requestAnimationFrame(() => lastImageButton.current?.focus());
  }

  const hasResults = sections.some((section) => section.topics.length > 0);

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div className={styles.breadcrumb}><Link to="/admin/dashboard">Admin</Link><span aria-hidden="true">/</span><span>User Manual</span></div>
        <div className={styles.headingRow}>
          <div>
            <p className={styles.kicker}>EquiConnected · Admin Portal</p>
            <h1>User Manual</h1>
            <p className={styles.intro}>A practical guide to the tools, workflows, and reports in your portal.</p>
          </div>
          <span className={styles.updated}>QUICK REFERENCE <i aria-hidden="true" /></span>
        </div>
      </header>

      <div className={styles.layout}>
        <aside className={styles.sidebar} aria-label="Manual contents">
          <label className={styles.searchLabel} htmlFor="manual-search">Find in the manual</label>
          <div className={styles.searchBox}>
            <span aria-hidden="true">⌕</span>
            <input id="manual-search" type="search" value={search} placeholder="Search topics, steps…" onChange={(event) => setSearch(event.target.value)} />
            {search && <button type="button" aria-label="Clear search" onClick={() => setSearch('')}>×</button>}
          </div>
          <details className={styles.contentsDisclosure} open>
            <summary className={styles.contentsSummary}>Browse topics</summary>
            <nav className={styles.contents} aria-label="Manual table of contents">
            {sections.filter((section) => section.topics.length > 0).map((section) => (
              <div className={styles.contentsGroup} key={section.title}>
                <a className={styles.sectionLink} href={`#section-${section.title.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`} onClick={() => setSearch('')}>{section.title}</a>
                {section.topics.map((topic) => (
                  <a className={styles.topicLink} key={topic.id} href={`#${topic.id}`} onClick={() => setSearch('')}>
                    {topic.title}
                  </a>
                ))}
              </div>
            ))}
            {!hasResults && <p className={styles.tocEmpty}>No matching topics.</p>}
            </nav>
          </details>
          <p className={styles.sideNote}><span aria-hidden="true">i</span> Workflows can vary with your account permissions.</p>
        </aside>

        <div className={styles.reader} aria-live="polite">
          {!hasResults && (
            <div className={styles.noResults} role="status">
              <span className={styles.noResultsMark} aria-hidden="true">⌕</span>
              <h2>No matching topics</h2>
              <p>Try another phrase or clear your search to browse the full manual.</p>
              <button type="button" onClick={() => setSearch('')}>Clear filters</button>
            </div>
          )}
          {sections.filter((section) => section.topics.length > 0).map((section) => (
            <section className={styles.section} key={section.title} aria-labelledby={`section-${section.title.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`}>
              <div className={styles.sectionHeading}>
                <span className={styles.sectionIndex}>{String(SECTIONS.findIndex((item) => item.title === section.title) + 1).padStart(2, '0')}</span>
                <h2 id={`section-${section.title.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`}>{section.title}</h2>
                <span className={styles.sectionCount}>{section.topics.length} {section.topics.length === 1 ? 'topic' : 'topics'}</span>
              </div>
              {section.topics.map((topic) => (
                <article className={styles.topic} id={topic.id} key={topic.id} tabIndex={-1}>
                  <h3>{topic.title}</h3>
                  <p className={styles.purpose}>{topic.purpose}</p>
                  <div className={styles.meta}>
                    <p><span>WHERE</span>{topic.where}</p>
                    <p><span>WHO</span>{topic.who}</p>
                  </div>
                  {topic.prerequisites.length > 0 && <div className={styles.topicBlock}><h4>Before you begin</h4><ul>{topic.prerequisites.map((item) => <li key={item}>{item}</li>)}</ul></div>}
                  <div className={styles.topicBlock}>
                    <h4>Steps</h4>
                    <ol>{topic.steps.map((step, index) => <li key={`${index}-${step}`}><span>{String(index + 1).padStart(2, '0')}</span>{step.replace(/^\s*(?:\d+[.)]|\(\d+\))\s+/, '')}</li>)}</ol>
                  </div>
                  <div className={styles.outcome}><span>RESULT</span><p>{topic.result}</p></div>
                  {topic.restrictions.length > 0 && <div className={styles.restrictions}><strong>Keep in mind</strong><ul>{topic.restrictions.map((item) => <li key={item}>{item}</li>)}</ul></div>}
                  {!!topic.images?.length && <div className={styles.figures}>{topic.images.map((image, index) => (
                    <figure key={`${image.src}-${index}`}>
                      <button type="button" className={styles.figureButton} aria-label={`Enlarge image: ${image.caption}`} onClick={(event) => { lastImageButton.current = event.currentTarget; setShowImageFullSize(false); setSelectedImage(image); }}>
                        <img src={image.src} alt={image.alt} loading="lazy" />
                        <span className={styles.enlargeLabel}>View larger <span aria-hidden="true">↗</span></span>
                      </button>
                      <figcaption>{image.caption}</figcaption>
                    </figure>
                  ))}</div>}
                </article>
              ))}
            </section>
          ))}
        </div>
      </div>
      <dialog ref={dialogRef} className={styles.imageDialog} aria-label="Enlarged manual screenshot" onCancel={(event) => { event.preventDefault(); closeImage(); }} onKeyDown={(event) => { if (event.key === 'Escape') { event.preventDefault(); closeImage(); } }} onClose={() => { if (selectedImage) closeImage(); }}>
        {selectedImage && <div className={styles.dialogFrame}>
          <div className={styles.dialogTop}>
            <p>{selectedImage.caption}</p>
            <div className={styles.dialogActions}>
              <button type="button" aria-pressed={showImageFullSize} onClick={() => setShowImageFullSize((fullSize) => !fullSize)}>{showImageFullSize ? 'Fit to window' : 'Show full size'}</button>
              <button type="button" aria-label="Close enlarged image" onClick={closeImage}>Close <span aria-hidden="true">×</span></button>
            </div>
          </div>
          <div className={`${styles.zoomViewport} ${showImageFullSize ? styles['zoomViewport--fullSize'] : ''}`}><img src={selectedImage.src} alt={selectedImage.alt} /></div>
          <p className={styles.dialogHint}>{showImageFullSize ? 'Full-size image · scroll horizontally and vertically to inspect' : 'Fitted to window · choose Show full size to inspect original pixels'}</p>
        </div>}
      </dialog>
    </div>
  );
}