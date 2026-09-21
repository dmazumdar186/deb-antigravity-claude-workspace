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
import { activeStepIndex, drumStepState, folioCardState, folioFrontIndex, heroFrame, sectionProgress } from '@/lib/motion';

export default function MotionController() {
  useEffect(() => {
    const reduceMotionQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    let reduceMotion = reduceMotionQuery.matches;
    const desktopMotion = window.matchMedia('(min-width: 800px)');

    // --- reveal-on-scroll for [data-reveal] sections not already using the
    // React <Reveal> component (kept for parity with the reference's pattern
    // and for any future plain-HTML section). ---
    const revealItems = Array.from(document.querySelectorAll<HTMLElement>('[data-reveal]'));
    let revealObserver: IntersectionObserver | null = null;
    if (revealItems.length) {
      if (reduceMotion || !('IntersectionObserver' in window)) {
        revealItems.forEach((el) => el.classList.add('is-visible'));
      } else {
        revealObserver = new IntersectionObserver(
          (entries) => {
            entries.forEach((entry) => {
              if (!entry.isIntersecting) return;
              entry.target.classList.add('is-visible');
              revealObserver?.unobserve(entry.target);
            });
          },
          { rootMargin: '0px 0px -10% 0px', threshold: 0.06 }
        );
        revealItems.forEach((el) => revealObserver?.observe(el));
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

    // Clears every motion custom property this controller has ever written to
    // the folio cards / drum steps, and restores the header progress + hero
    // step-rail fill to their rest values. Called when prefers-reduced-motion
    // flips on mid-session (content must show fully, unanimated) and when the
    // desktop breakpoint is left (the stacked mobile layout must never carry
    // stale --folio-*/--drum-* values, even though globals.css's mobile
    // media-query rules already `!important`-override them defensively).
    const clearFolioAndDrumProps = () => {
      folioCards.forEach((card) => {
        card.style.removeProperty('--folio-x');
        card.style.removeProperty('--folio-y');
        card.style.removeProperty('--folio-rotation');
        card.style.removeProperty('--folio-scale');
        card.style.removeProperty('--folio-opacity');
        card.style.removeProperty('--folio-caption-opacity');
        card.style.removeProperty('--folio-body-opacity');
        card.removeAttribute('data-folio-front');
        card.style.removeProperty('z-index');
      });
      approachSteps.forEach((step) => {
        step.style.removeProperty('--drum-y');
        step.style.removeProperty('--drum-rotate');
        step.style.removeProperty('--drum-scale');
        step.style.removeProperty('--drum-opacity');
        step.removeAttribute('aria-current');
      });
    };

    // Shows every hero copy state and clears the accessibility-hiding on the
    // off states (all become visually visible via the reduced-motion CSS
    // block regardless of `is-on`, so the a11y tree must match).
    const showAllHeroStates = () => {
      currentHeroState = -1;
      heroStates.forEach((el) => {
        el.classList.add('is-on');
        el.removeAttribute('aria-hidden');
      });
      heroBgs.forEach((el) => el.classList.add('is-on'));
      heroSteps.forEach((el) => el.style.setProperty('--fill', '1'));
    };

    const update = () => {
      scheduled = false;
      const viewport = window.innerHeight;

      // --- READ PHASE: gather every layout metric first (scrollHeight,
      // scrollY, getBoundingClientRect x3) before any style write below, so
      // a single frame only forces layout once instead of interleaving
      // reads and writes into three separate synchronous layouts. ---
      const pageRange = header ? Math.max(document.documentElement.scrollHeight - viewport, 1) : 0;
      const scrollY = window.scrollY;
      const heroRect = hero && heroStates.length ? hero.getBoundingClientRect() : null;
      const runFolio = !reduceMotion && desktopMotion.matches && !!folio && folioCards.length > 0;
      const folioRect = runFolio ? folio!.getBoundingClientRect() : null;
      const runApproach = !reduceMotion && desktopMotion.matches && !!approach && approachSteps.length > 0;
      const approachRect = runApproach ? approach!.getBoundingClientRect() : null;

      // --- WRITE PHASE: apply every DOM mutation using only the locals
      // captured above; nothing below re-reads layout. ---
      if (header) {
        const pageProgress = Math.min(1, Math.max(0, scrollY / pageRange));
        header.classList.toggle('is-scrolled', scrollY > 24);
        header.style.setProperty('--page-progress', String(pageProgress));
      }

      if (heroRect) {
        const progress = sectionProgress(heroRect, viewport);
        const frame = heroFrame(progress, heroStates.length);
        if (frame.stateIndex !== currentHeroState) {
          currentHeroState = frame.stateIndex;
          heroStates.forEach((el) => {
            const isOn = Number(el.dataset.heroState) === currentHeroState;
            el.classList.toggle('is-on', isOn);
            el.setAttribute('aria-hidden', String(!isOn));
          });
          heroBgs.forEach((el) => {
            el.classList.toggle('is-on', Number(el.dataset.heroBg) === currentHeroState);
          });
        }
        heroSteps.forEach((el, i) => el.style.setProperty('--fill', frame.fill[i]?.toFixed(3) ?? '0'));
      }

      if (folioRect) {
        const progress = sectionProgress(folioRect, viewport);
        const frontIndex = folioFrontIndex(progress, folioCards.length);
        folioCards.forEach((card, index) => {
          const state = folioCardState(progress, index, folioCards.length);
          // The 800-1200px two-line headline clamp is the pure-CSS default
          // (globals.css); this attribute only lets the BACK cards opt down to a
          // one-line tab strip (`html.has-js .folio-card:not([data-folio-front])`).
          if (index === frontIndex) card.setAttribute('data-folio-front', '');
          else card.removeAttribute('data-folio-front');
          card.style.setProperty('--folio-x', `${state.xPercent}%`);
          card.style.setProperty('--folio-y', `${state.yPercent}%`);
          card.style.setProperty('--folio-rotation', `${state.rotationDeg}deg`);
          card.style.setProperty('--folio-scale', String(state.scale));
          card.style.setProperty('--folio-opacity', String(state.opacity));
          card.style.setProperty('--folio-caption-opacity', String(state.captionOpacity));
          card.style.setProperty('--folio-body-opacity', String(state.bodyOpacity));
          card.style.zIndex = String(state.zIndex);
        });
      }

      if (approachRect) {
        const progress = sectionProgress(approachRect, viewport);
        const active = activeStepIndex(progress, approachSteps.length);
        approach!.style.setProperty('--approach-progress', `${progress * 100}%`);
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

    const handleReduceMotionChange = (e: MediaQueryListEvent) => {
      reduceMotion = e.matches;
      if (reduceMotion) {
        clearFolioAndDrumProps();
        showAllHeroStates();
      }
      schedule();
    };

    const handleDesktopMotionChange = () => {
      if (!desktopMotion.matches) {
        clearFolioAndDrumProps();
      }
      schedule();
    };

    window.addEventListener('scroll', schedule, { passive: true });
    window.addEventListener('resize', schedule);
    desktopMotion.addEventListener?.('change', handleDesktopMotionChange);
    reduceMotionQuery.addEventListener?.('change', handleReduceMotionChange);
    update();

    return () => {
      window.removeEventListener('scroll', schedule);
      window.removeEventListener('resize', schedule);
      desktopMotion.removeEventListener?.('change', handleDesktopMotionChange);
      reduceMotionQuery.removeEventListener?.('change', handleReduceMotionChange);
      revealObserver?.disconnect();
    };
  }, []);

  return null;
}
