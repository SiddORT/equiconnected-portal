import { useLayoutEffect, useState, type RefObject } from 'react';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

const REDUCED_MOTION_QUERY = '(prefers-reduced-motion: reduce)';

function getReducedMotionPreference() {
  return typeof window !== 'undefined'
    && typeof window.matchMedia === 'function'
    && window.matchMedia(REDUCED_MOTION_QUERY).matches;
}

/**
 * Coordinates the small, performance-friendly motion layer for the public home.
 * Components opt into a behavior with data attributes so content and structure
 * remain independent from the animation implementation.
 */
export function usePublicPageAnimations(rootRef: RefObject<HTMLElement | null>) {
  const [reducedMotion, setReducedMotion] = useState(getReducedMotionPreference);

  useLayoutEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return undefined;

    const mediaQuery = window.matchMedia(REDUCED_MOTION_QUERY);
    const updatePreference = () => setReducedMotion(mediaQuery.matches);
    mediaQuery.addEventListener?.('change', updatePreference);

    return () => mediaQuery.removeEventListener?.('change', updatePreference);
  }, []);

  useLayoutEffect(() => {
    const root = rootRef.current;
    if (
      !root
      || typeof window === 'undefined'
      || typeof window.matchMedia !== 'function'
    ) return undefined;

    gsap.registerPlugin(ScrollTrigger);
    const hoverCleanups: Array<() => void> = [];
    const context = gsap.context(() => {
      if (reducedMotion) return;

      const heroItems = root.querySelectorAll<HTMLElement>('[data-hero-item]');
      const heroMedia = root.querySelector<HTMLElement>('[data-hero-media]');
      const header = root.querySelector<HTMLElement>('[data-motion-header]');

      const heroTimeline = gsap.timeline({
        defaults: { ease: 'power3.out' },
      });

      if (header) {
        heroTimeline.fromTo(
          header,
          { autoAlpha: 0, y: -12 },
          { autoAlpha: 1, y: 0, duration: 0.55 },
          0,
        );
      }

      if (heroMedia) {
        heroTimeline.fromTo(
          heroMedia,
          { autoAlpha: 0, x: 26, scale: 0.985 },
          { autoAlpha: 1, x: 0, scale: 1, duration: 0.9 },
          0.12,
        );
      }

      if (heroItems.length > 0) {
        heroTimeline.fromTo(
          heroItems,
          { autoAlpha: 0, y: 24 },
          {
            autoAlpha: 1,
            y: 0,
            duration: 0.68,
            stagger: 0.075,
          },
          0.2,
        );
      }

      const aboutSection = root.querySelector<HTMLElement>('[data-about-section]');
      const aboutImage = aboutSection?.querySelector<HTMLElement>('[data-about-image]');
      const aboutCopy = aboutSection?.querySelector<HTMLElement>('[data-about-copy]');
      if (aboutSection && aboutImage && aboutCopy) {
        const aboutTimeline = gsap.timeline({
          defaults: { ease: 'power3.out' },
          scrollTrigger: {
            trigger: aboutSection,
            start: 'top 80%',
            once: true,
            invalidateOnRefresh: true,
          },
        });

        aboutTimeline
          .fromTo(
            aboutImage,
            { autoAlpha: 0, y: 34, scale: 0.94 },
            { autoAlpha: 1, y: 0, scale: 1, duration: 0.82 },
            0,
          )
          .fromTo(
            aboutCopy,
            { autoAlpha: 0, y: 24 },
            { autoAlpha: 1, y: 0, duration: 0.7 },
            0.28,
          );
      }

      root.querySelectorAll<HTMLElement>('[data-scroll-reveal]').forEach((element) => {
        gsap.fromTo(
          element,
          { autoAlpha: 0, y: 28 },
          {
            autoAlpha: 1,
            y: 0,
            duration: 0.72,
            ease: 'power2.out',
            scrollTrigger: {
              trigger: element,
              start: 'top 86%',
              once: true,
              invalidateOnRefresh: true,
            },
          },
        );
      });

      root.querySelectorAll<HTMLElement>('[data-scroll-stagger]').forEach((group) => {
        const children = group.querySelectorAll<HTMLElement>('[data-stagger-item]');
        if (children.length === 0) return;

        gsap.fromTo(
          children,
          { autoAlpha: 0, y: 20 },
          {
            autoAlpha: 1,
            y: 0,
            duration: 0.55,
            stagger: 0.08,
            ease: 'power2.out',
            scrollTrigger: {
              trigger: group,
              start: 'top 84%',
              once: true,
              invalidateOnRefresh: true,
            },
          },
        );
      });

      const parallaxElement = root.querySelector<HTMLElement>('[data-subtle-parallax]');
      const parallaxTrigger = parallaxElement?.closest<HTMLElement>('[data-parallax-trigger]');
      if (parallaxElement && parallaxTrigger) {
        gsap.fromTo(
          parallaxElement,
          { yPercent: 5 },
          {
            yPercent: -5,
            ease: 'none',
            scrollTrigger: {
              trigger: parallaxTrigger,
              start: 'top bottom',
              end: 'bottom top',
              scrub: true,
              invalidateOnRefresh: true,
            },
          },
        );
      }

      root.querySelectorAll<HTMLElement>('[data-gsap-hover]').forEach((element) => {
        const enter = () => {
          gsap.to(element, {
            y: -3,
            scale: 1.012,
            duration: 0.24,
            ease: 'power2.out',
            overwrite: 'auto',
          });
        };
        const leave = () => {
          gsap.to(element, {
            y: 0,
            scale: 1,
            duration: 0.3,
            ease: 'power2.out',
            overwrite: 'auto',
          });
        };

        element.addEventListener('pointerenter', enter);
        element.addEventListener('pointerleave', leave);
        hoverCleanups.push(() => {
          element.removeEventListener('pointerenter', enter);
          element.removeEventListener('pointerleave', leave);
        });
      });

    }, root);
    context.add(() => hoverCleanups.forEach((cleanup) => cleanup()));

    return () => context.revert();
  }, [reducedMotion, rootRef]);
}