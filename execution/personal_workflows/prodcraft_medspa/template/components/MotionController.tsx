'use client';

// components/MotionController.tsx
// description: One mount-once controller that drives every scroll-scrubbed
//   effect on the page — the header page-progress bar, the hero's numbered
//   copy states + step rail, the sticky folio card fan-out, and the "your
//   visit" drum. Technique ported (not copied) from a reference site's
//   vanilla-JS approach: query DOM nodes by data-attribute, compute state
//   with lib/motion.ts's pure functions, and write results back as CSS
//   custom properties / classes directly (no per-frame React re-render).
//   A single rAF-scheduled, passive scroll listener; no motion library. Gated
//   behind prefers-reduced-motion (bails out entirely — CSS makes every
//   affected section render fully visible with no transform in that case, and
//   for browsers without JS at all, see the `html:not(.has-js)` rules in
//   globals.css) and a desktop matchMedia for the folio/drum 3D transforms
//   only (they fall back to a plain stacked layout below that breakpoint).
// inputs: none (reads the live DOM)
// outputs: none (side effects only — CSS custom properties + classes)

import { useEffect } from 'react';
import { activeStepIndex, drumStepState, folioCardState, heroFrame, sectionProgress } from '@/lib/motion';

export default function MotionController() {
  useEffect(() => {
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const desktopMotion = window.matchMedia('(min-width: 800px)');

    // --- reveal-on-scroll for [data-reveal] sections not already using the
    // React <Reveal> component (kept for parity with the reference's pattern
    // and for any future plain-HTML section). ---
    const revealItems = Array.from(document.querySelectorAll<HTMLElement>('[data-reveal]'));
    if (revealItems.length) {
      if (reduceMotion || !('IntersectionObserver' in window)) {
        revealItems.forEach((el) => el.classList.add('is-visible'));
      } else {
        const observer = new IntersectionObserver(
          (entries) => {
            entries.forEach((entry) => {
              if (!entry.isIntersecting) return;
              entry.target.classList.add('is-visible');
              observer.unobserve(entry.target);
            });
          },
          { rootMargin: '0px 0px -10% 0px', threshold: 0.06 }
        );
        revealItems.forEach((el) => observer.observe(el));
      }
    }

    const header = document.querySelector<HTMLElement>('[data-header]');
    const hero = document.querySelector<HTMLElement>('[data-hero]');
    const heroStates = Array.from(document.querySelectorAll<HTMLElement>('[data-hero-state]'));
    const heroSteps = Array.from(document.querySelectorAll<HTMLElement>('[data-hero-step]'));
    const heroBgs = Array.from(document.querySelectorAll<HTMLElement>('[data-hero-bg]'));
    const folio = document.querySelector<HTMLElement>('[data-folio]');
    const folioCards = Array.from(document.querySelectorAll<HTMLElement>('[data-folio-card]'));
    const approach = document.querySelector<HTMLElement>('[data-approach]');
    const approachSteps = Array.from(document.querySelectorAll<HTMLElement>('[data-approach-step]'));

    let currentHeroState = -1;
    let scheduled = false;

    const update = () => {
      scheduled = false;
      const viewport = window.innerHeight;

      if (header) {
        const pageRange = Math.max(document.documentElement.scrollHeight - viewport, 1);
        const pageProgress = Math.min(1, Math.max(0, window.scrollY / pageRange));
        header.classList.toggle('is-scrolled', window.scrollY > 24);
        header.style.setProperty('--page-progress', String(pageProgress));
      }

      if (hero && heroStates.length) {
        const rect = hero.getBoundingClientRect();
        const progress = sectionProgress(rect, viewport);
        const frame = heroFrame(progress, heroStates.length);
        if (frame.stateIndex !== currentHeroState) {
          currentHeroState = frame.stateIndex;
          heroStates.forEach((el) => {
            el.classList.toggle('is-on', Number(el.dataset.heroState) === currentHeroState);
          });
          heroBgs.forEach((el) => {
            el.classList.toggle('is-on', Number(el.dataset.heroBg) === currentHeroState);
          });
        }
        heroSteps.forEach((el, i) => el.style.setProperty('--fill', frame.fill[i]?.toFixed(3) ?? '0'));
      }

      if (!reduceMotion && desktopMotion.matches && folio && folioCards.length) {
        const progress = sectionProgress(folio.getBoundingClientRect(), viewport);
        folioCards.forEach((card, index) => {
          const state = folioCardState(progress, index, folioCards.length);
          card.style.setProperty('--folio-x', `${state.xPercent}%`);
          card.style.setProperty('--folio-y', `${state.yPercent}%`);
          card.style.setProperty('--folio-rotation', `${state.rotationDeg}deg`);
          card.style.setProperty('--folio-scale', String(state.scale));
          card.style.setProperty('--folio-opacity', String(state.opacity));
          card.style.setProperty('--folio-caption-opacity', String(state.captionOpacity));
          card.style.zIndex = String(state.zIndex);
        });
      }

      if (!reduceMotion && desktopMotion.matches && approach && approachSteps.length) {
        const progress = sectionProgress(approach.getBoundingClientRect(), viewport);
        const active = activeStepIndex(progress, approachSteps.length);
        approach.style.setProperty('--approach-progress', `${progress * 100}%`);
        approachSteps.forEach((step, index) => {
          const state = drumStepState(progress, index, approachSteps.length);
          step.style.setProperty('--drum-y', `${state.yPercent}%`);
          step.style.setProperty('--drum-rotate', `${state.rotationX}deg`);
          step.style.setProperty('--drum-scale', String(state.scale));
          step.style.setProperty('--drum-opacity', String(state.opacity));
          if (index === active) step.setAttribute('aria-current', 'step');
          else step.removeAttribute('aria-current');
        });
      }
    };

    const schedule = () => {
      if (scheduled) return;
      scheduled = true;
      requestAnimationFrame(update);
    };

    window.addEventListener('scroll', schedule, { passive: true });
    window.addEventListener('resize', schedule);
    desktopMotion.addEventListener?.('change', schedule);
    update();

    return () => {
      window.removeEventListener('scroll', schedule);
      window.removeEventListener('resize', schedule);
      desktopMotion.removeEventListener?.('change', schedule);
    };
  }, []);

  return null;
}
