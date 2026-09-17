'use strict';
/* Header, menu, reveals, the pinned search-process stack, and the contact
   forms. Every block bails out quietly if its markup is not on the page, so
   the same file serves all five pages. */

(function initSite() {
  var M = window.GaiaMotion;
  var reduce = window.matchMedia('(prefers-reduced-motion: reduce)');
  var desktop = window.matchMedia('(min-width: 800px)');

  /* ------------------------------------------------- header + progress */
  var hdr = document.querySelector('[data-header]');
  var stack = document.querySelector('[data-stack]');
  var cards = stack ? Array.prototype.slice.call(stack.querySelectorAll('[data-card]')) : [];
  var stackSteps = stack ? Array.prototype.slice.call(stack.querySelectorAll('[data-stack-step]')) : [];

  /* One scroll progress drives both the card transforms and the step rail. */
  function paintStack(p) {
    var position = p * Math.max(cards.length - 1, 0);
    cards.forEach(function (el, i) {
      var s = M.stackCardState(p, i, cards.length);
      var hidden = s.opacity < 0.08;
      el.style.setProperty('--card-y', s.yPercent.toFixed(2) + '%');
      el.style.setProperty('--card-rot', s.rotationDeg.toFixed(2) + 'deg');
      el.style.setProperty('--card-scale', s.scale.toFixed(3));
      el.style.setProperty('--card-opacity', s.opacity.toFixed(3));
      el.style.zIndex = String(s.zIndex);
      el.classList.toggle('is-front', s.isFront);
      el.setAttribute('aria-hidden', hidden ? 'true' : 'false');
      el.inert = hidden;
      var step = stackSteps[i];
      if (!step) return;
      step.style.setProperty('--fill', M.clamp01(position - i + 1).toFixed(3));
      step.classList.toggle('is-on', s.isFront);
      if (s.isFront) step.setAttribute('aria-current', 'step');
      else step.removeAttribute('aria-current');
    });
  }
  if (stack) stack.style.setProperty('--stack-span', String(cards.length));

  var pending = false;
  var stackFrozen = false;
  function update() {
    pending = false;
    var vh = window.innerHeight;
    if (hdr) {
      var range = Math.max(document.documentElement.scrollHeight - vh, 1);
      hdr.classList.toggle('is-scrolled', window.scrollY > 48);
      hdr.style.setProperty('--page-progress', String(Math.min(1, Math.max(0, window.scrollY / range))));
    }
    /* stackFrozen: index.html?stack=<p> pins the stack for a screenshot; a
       resize (viewport rotate, devtools opening) must not repaint it back
       onto the live scroll progress. Outside desktop-motion mode the cards
       render as a plain stacked list (CSS handles the layout), so clear any
       inert/aria-hidden a previous desktop paintStack() left behind, or a
       resize down from desktop can leave cards keyboard/AT-unreachable. */
    if (stackFrozen) {
      /* no-op */
    } else if (M && stack && cards.length && desktop.matches && !reduce.matches) {
      paintStack(M.sectionProgress(stack.getBoundingClientRect(), vh));
    } else if (cards.length) {
      var props = ['--card-y', '--card-rot', '--card-scale', '--card-opacity', 'z-index'];
      cards.forEach(function (el) {
        el.removeAttribute('aria-hidden');
        el.inert = false;
        el.classList.remove('is-front');
        props.forEach(function (p) { el.style.removeProperty(p); });
      });
      stackSteps.forEach(function (s) {
        s.classList.remove('is-on');
        s.removeAttribute('aria-current');
        s.style.removeProperty('--fill');
      });
    }
  }
  function onScroll() {
    if (pending) return;
    pending = true;
    requestAnimationFrame(update);
  }
  window.addEventListener('scroll', onScroll, { passive: true });
  window.addEventListener('resize', onScroll);
  update();

  /* Review hook, matching the hero's: index.html?stack=0.5 freezes the pinned
     search-process stack at that progress so a still can be captured. */
  (function freezeStack() {
    var hook = /[?&]stack=([0-9.]+)/.exec(window.location.search || '');
    if (!hook || !stack || !cards.length || !M) return;
    if (!desktop.matches || reduce.matches) return;
    window.removeEventListener('scroll', onScroll);
    stackFrozen = true;
    paintStack(Math.min(1, Math.max(0, parseFloat(hook[1]) || 0)));
  }());

  /* ------------------------------------------------------------ menu */
  var toggle = document.querySelector('[data-menu-toggle]');
  var menu = document.querySelector('[data-menu]');
  if (toggle && menu) {
    /* The header and the footer are siblings of <main>, so inerting <main>
       alone leaves both of them tabbable behind the open menu. Inert every
       top-level element except the menu — and except the header, which carries
       the close button and is lifted above the overlay while it is open. The
       header's own nav is display:none at these widths, so all it exposes is
       the logo and the toggle. */
    var header = toggle.closest('header') || document.querySelector('[data-header]');
    var siblings = Array.prototype.filter.call(document.body.children, function (el) {
      return el !== menu && el !== header;
    });
    var restoreTo = null;
    var setMenu = function (open) {
      if (open) restoreTo = document.activeElement;
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
      toggle.setAttribute('aria-label', (open ? toggle.dataset.labelClose : toggle.dataset.labelOpen) || 'Menu');
      menu.classList.toggle('is-open', open);
      menu.inert = !open;
      document.body.style.overflow = open ? 'hidden' : '';
      document.body.classList.toggle('is-menu-open', open);
      siblings.forEach(function (el) { el.inert = open; });
      if (open) {
        /* `menu.inert = false` and the `.is-open` class (which drives the
           menu's visibility) were just set above, but the browser does not
           consider the menu's contents focusable until it has actually
           applied that style/inert change during its next "update the
           rendering" step — a focus() call before that step (same tick,
           or even a single setTimeout(0)/requestAnimationFrame later, which
           can both still land before that step runs) silently no-ops and
           leaves focus on the toggle. Two nested rAFs guarantee at least
           one full render step has happened first. */
        window.requestAnimationFrame(function () {
          window.requestAnimationFrame(function () {
            var first = menu.querySelector('a, button');
            if (first) first.focus();
          });
        });
      } else {
        var target = (restoreTo && document.contains(restoreTo)) ? restoreTo : toggle;
        restoreTo = null;
        if (target && target.focus) target.focus();
      }
    };
    menu.inert = true;
    toggle.addEventListener('click', function () {
      setMenu(toggle.getAttribute('aria-expanded') !== 'true');
    });
    menu.addEventListener('click', function (e) {
      if (e.target.closest('a')) setMenu(false);
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && toggle.getAttribute('aria-expanded') === 'true') setMenu(false);
    });
  }

  /* --------------------------------------------------------- reveals */
  var items = Array.prototype.slice.call(document.querySelectorAll('[data-reveal]'));
  if (items.length) {
    if (reduce.matches || !('IntersectionObserver' in window)) {
      items.forEach(function (el) { el.classList.add('is-visible'); });
    } else {
      var obs = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (!entry.isIntersecting) return;
          entry.target.classList.add('is-visible');
          obs.unobserve(entry.target);
        });
      }, { rootMargin: '0px 0px -8% 0px', threshold: 0.08 });
      items.forEach(function (el) { obs.observe(el); });
      /* Safety net for renderers that never run the observer — a background
         tab, a headless screenshot, a print job. It must not fire for someone
         actually looking at the page, or every reveal below the fold is spent
         before they reach it. */
      window.setTimeout(function () {
        /* Unconditional after 20s: no visibilityState gate. hasFocus() and
           visibilityState are both unreliable in a headless/CI runner, which
           can hold OS-level focus and 'visible' state on its own window while
           the tab it drives never scrolls anything into view — that used to
           make this net either fire immediately or never fire at all,
           depending on the runner. 20s is short enough to still catch a
           genuinely abandoned render (a background tab, a print job) but
           long enough that a normal page visit, or a test driving several
           seconds of scroll interaction first, never needs it (the
           observer will already have revealed everything by then). */
        items.forEach(function (el) { el.classList.add('is-visible'); });
        obs.disconnect();
      }, 20000);
    }
  }

  /* ----------------------------------------------------------- forms */
  function compose(form) {
    var lines = [];
    var fields = form.querySelectorAll('input, select, textarea');
    Array.prototype.forEach.call(fields, function (f) {
      if (!f.name || f.type === 'submit') return;
      if (f.type === 'radio' && !f.checked) return;
      var value = (f.value || '').trim();
      if (!value) return;
      var byId = null;
      if (f.id) {
        var sel = window.CSS && CSS.escape ? CSS.escape(f.id) : f.id.replace(/["\\]/g, '\\$&');
        byId = form.querySelector('label[for="' + sel + '"]');
      }
      var label = f.dataset.label || (byId || {}).textContent || f.name;
      lines.push(String(label).replace(/\s+/g, ' ').trim() + ': ' + value);
    });
    return lines.join('\n');
  }

  Array.prototype.forEach.call(document.querySelectorAll('[data-compose]'), function (form) {
    var out = document.getElementById(form.dataset.compose);
    if (!out) return;
    var pre = out.querySelector('pre');
    if (!pre) return;
    var copy = out.querySelector('[data-copy]');
    var mail = out.querySelector('[data-mail]');
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var text = compose(form);
      pre.textContent = text;
      out.classList.add('is-on');
      var address = (document.body.dataset.contactEmail || '').trim();
      if (mail) {
        if (address) {
          /* Long mailto URLs are silently truncated or refused by some clients;
             the full message is on the page either way. */
          var body = text.length > 1500 ? text.slice(0, 1500) + '\n\n[…]' : text;
          mail.href = 'mailto:' + address
            + '?subject=' + encodeURIComponent(form.dataset.subject || 'Website enquiry')
            + '&body=' + encodeURIComponent(body);
          mail.hidden = false;
        } else {
          mail.hidden = true;
        }
      }
      out.setAttribute('tabindex', '-1');
      out.focus({ preventScroll: false });
    });
    if (copy) {
      var copyTimer = 0;
      copy.addEventListener('click', function () {
        var text = pre.textContent;
        var done = function () {
          var span = copy.querySelector('.btn__t') || copy;
          if (!span.dataset.label) span.dataset.label = span.textContent;
          span.textContent = 'Copied';
          window.clearTimeout(copyTimer);
          copyTimer = window.setTimeout(function () {
            span.textContent = span.dataset.label;
          }, 2200);
        };
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(text).then(done, function () { fallback(text, done); });
        } else {
          fallback(text, done);
        }
      });
    }
    function fallback(text, done) {
      var ta = document.createElement('textarea');
      ta.value = text;
      ta.setAttribute('readonly', '');
      ta.style.cssText = 'position:fixed;top:-1000px;opacity:0';
      document.body.appendChild(ta);
      ta.select();
      try {
        document.execCommand('copy');
        done();
      } catch (err) {
        /* Clipboard is unavailable (file:// or a locked-down browser). The
           message is already on screen and selectable, so leave it be —
           logged rather than swallowed silently. */
        if (window.console) window.console.warn('Copy unavailable:', err);
      }
      document.body.removeChild(ta);
    }
  });
}());
