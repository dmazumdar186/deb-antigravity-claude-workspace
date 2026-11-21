'use strict';
/* Platform Worker client for the static boards: the live job set (insights charts, board search) and the
   job-alert / newsletter sign-up forms. The API lives on the board's own host in production (data-live-api="1",
   empty data-api-base) and on the Worker's own origin on staging (data-api-base="https://..."); a page with
   neither (the static demo) never calls it.
   - Live jobs: GET /api/jobs?view=board&site=<ed>, followed page by page (floor 1, ceiling MAX_PAGES), cached in
     sessionStorage for at most 5 minutes. The build-time #gj-data stays the no-JS and failure fallback (advice:
     any error keeps it, silently).
   - Sign-ups: GET /api/config tells whether ALERTS_ENABLED / NEWSLETTER_ENABLED are on. Off, unknown or no API:
     the form says "coming soon" and posts nothing. On: POST JSON (the Worker's CSRF rule: JSON only, CORS
     allow-list, honeypot, rate limit, double opt-in) and an accessible status / field error.
   Pure helpers are exported for node --test (api.test.js). */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.GJApi = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  var TTL_MS = 5 * 60 * 1000, MAX_PAGES = 40, PAGE = 500;
  var BASE_RE = /^https:\/\/[a-z0-9.-]+$/i;

  /* null = no API on this page; '' = same origin; else the Worker origin. */
  function apiBase(body) {
    if (!body || body.getAttribute('data-live-api') !== '1') return null;
    var b = body.getAttribute('data-api-base') || '';
    return BASE_RE.test(b) ? b : '';
  }
  function getJson(fetchFn, url) {
    return fetchFn(url, { credentials: 'omit' }).then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    });
  }
  function cacheGet(store, key, now) {
    try {
      var v = JSON.parse(store.getItem(key) || 'null');
      return v && typeof v.t === 'number' && now - v.t >= 0 && now - v.t <= TTL_MS ? v.d : null;
    } catch (e) { return null; }
  }
  function cachePut(store, key, now, d) {
    try { store.setItem(key, JSON.stringify({ t: now, d: d })); } catch (e) { /* quota or private mode: just not cached */ }
  }

  /* Every page of the live set -> {today, total, jobs, facets}. Rejects on a broken chain or a set that changed
     between pages (total differs / jobs.length !== total), so a caller never shows half a board. */
  function loadJobs(fetchFn, base, site, opts) {
    opts = opts || {};
    var limit = opts.limit || PAGE, out = { jobs: [] }, pages = 0, seen = {};
    function url(after) {
      return base + '/api/jobs?view=board&site=' + site + '&limit=' + limit + (opts.text === false ? '&text=0' : '') + (after ? '&after=' + encodeURIComponent(after) : '');
    }
    function step(after) {
      if (++pages > MAX_PAGES) return Promise.reject(new Error('too many pages'));
      return getJson(fetchFn, url(after)).then(function (p) {
        if (!p || p.site !== site || !Array.isArray(p.jobs)) throw new Error('bad page');
        if (pages === 1) { out.today = p.today; out.total = p.total; out.facets = p.facets; }
        else if (p.total !== out.total) throw new Error('job set changed while paging');
        out.jobs = out.jobs.concat(p.jobs);
        if (p.next) {
          if (seen[p.next]) throw new Error('cursor loop');
          seen[p.next] = true;
          return step(p.next);
        }
        if (out.jobs.length !== out.total || !out.facets) throw new Error('incomplete set');
        return out;
      });
    }
    return step(null);
  }

  /* The live set in the #gj-data shape. A job the static tree also built keeps its static href and logo (the
     page exists on this host); a newer job links to the Worker-rendered page on the API origin. */
  function merge(stat, live, base) {
    var byId = {};
    (stat.jobs || []).forEach(function (j) { byId[j.id] = j; });
    var f = live.facets, jobs = live.jobs.map(function (j) {
      var s = byId[j.id], o = {}, k;
      for (k in j) if (Object.prototype.hasOwnProperty.call(j, k)) o[k] = j[k];
      if (s) { o.href = s.href; o.logo = s.logo; o.lw = s.lw; o.lh = s.lh; } else if (base) o.href = base + j.href;
      return o;
    });
    var d = {}, key;
    for (key in stat) if (Object.prototype.hasOwnProperty.call(stat, key)) d[key] = stat[key];
    d.today = live.today; d.jobs = jobs; d.sectors = f.sectors; d.regions = f.regions; d.types = f.types; d.contracts = f.contracts;
    d.live = true;
    return d;
  }

  /* Browser: the page's live dataset (or null: keep the build-time one). */
  function board(doc, withText) {
    var body = doc.body, base = apiBase(body), ed = body && body.getAttribute('data-edition'), el = doc.getElementById('gj-data');
    if (base === null || (ed !== 'ie' && ed !== 'uk') || !el || typeof fetch !== 'function') return Promise.resolve(null);
    var stat;
    try { stat = JSON.parse(el.textContent); } catch (e) { return Promise.resolve(null); }
    if (stat.live) return Promise.resolve(null); /* a Worker-rendered page is live already */
    var store = null;
    try { store = window.sessionStorage; } catch (e) { store = null; }
    var key = 'gj-live:' + ed + ':' + (withText ? 't' : 'n'), now = Date.now(), hit = store && cacheGet(store, key, now);
    var p = hit ? Promise.resolve(hit) : loadJobs(fetch.bind(window), base, ed, { text: withText }).then(function (live) { if (store) cachePut(store, key, now, live); return live; });
    return p.then(function (live) { return merge(stat, live, base); }).catch(function () { return null; });
  }

  /* ---- sign-ups */
  var COPY = {
    alerts: { soon: 'Job alerts by email are coming soon. Nothing was sent. Your address has not been stored.', done: 'Check your inbox: we have sent you a link to confirm this alert. Nothing is sent until you confirm.' },
    newsletter: { soon: 'The weekly newsletter is coming soon. Nothing was sent. Your address has not been stored.', done: 'Check your inbox: we have sent you a link to confirm. Nothing is sent until you confirm.' },
  };
  /* Worker answer -> {ok, text, field}. field: the input to mark aria-invalid. */
  function outcome(kind, status, body) {
    var e = body && body.error;
    if (status === 202) return { ok: true, text: COPY[kind].done };
    if (status === 404) return { ok: false, soon: true, text: COPY[kind].soon };
    if (e === 'invalid_email') return { ok: false, field: 'email', text: 'Please enter a valid email address, like name@example.com.' };
    if (e === 'invalid_query') return { ok: false, text: 'Please choose at most five sectors.' };
    if (status === 429) return { ok: false, text: 'Too many sign-ups from this connection. Please try again in 10 minutes.' };
    if (status === 503) return { ok: false, text: 'We could not send the confirmation email just now. Please try again later.' };
    return { ok: false, text: 'Not sent (' + (e || 'error ' + status) + '). Please try again.' };
  }
  function payload(kind, fields) {
    var b = { email: String(fields.email || '').trim(), consent: true, website: String(fields.website || '') };
    if (kind === 'alerts' && fields.sector) b.sectors = [String(fields.sector)];
    return b;
  }
  function post(fetchFn, base, kind, site, body) {
    var path = kind === 'alerts' ? '/api/alerts' : '/api/newsletter';
    return fetchFn(base + path + '?site=' + site, { method: 'POST', credentials: 'omit', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
      .then(function (r) { return r.json().catch(function () { return {}; }).then(function (d) { return { status: r.status, body: d }; }); });
  }

  function initForms(doc, fetchFn) {
    var forms = Array.prototype.slice.call(doc.querySelectorAll('form[data-signup]'));
    if (!forms.length) return null;
    var F = fetchFn || (typeof fetch === 'function' ? fetch.bind(window) : null);
    var body = doc.body, base = apiBase(body), ed = body.getAttribute('data-edition');
    var flagsP = base === null || !F || (ed !== 'ie' && ed !== 'uk') ? Promise.resolve({})
      : getJson(F, base + '/api/config?site=' + ed).catch(function () { return {}; });
    forms.forEach(function (f) {
      var kind = f.getAttribute('data-signup'), st = f.querySelector('[data-signup-status]'), email = f.querySelector('input[type="email"]');
      var err = f.querySelector('[data-signup-error]'), extra = f.querySelector('[data-signup-newsletter]'), btn = f.querySelector('[type="submit"]');
      function say(text, isErr) { st.textContent = text; st.classList.toggle('is-err', !!isErr); st.hidden = false; }
      function fieldError(text) {
        email.setAttribute('aria-invalid', 'true'); err.textContent = text; err.hidden = false; email.focus();
      }
      function clearError() { email.removeAttribute('aria-invalid'); err.textContent = ''; err.hidden = true; }
      flagsP.then(function (flags) { if (!flags[kind]) f.setAttribute('data-signup-off', ''); });
      f.addEventListener('submit', function (e) {
        e.preventDefault();
        clearError();
        return flagsP.then(function (flags) {
          if (!flags[kind]) { say(COPY[kind].soon); return; } /* flag off / no API: post nothing */
          if (!email.value.trim() || (email.checkValidity && !email.checkValidity())) { fieldError('Please enter a valid email address, like name@example.com.'); return; }
          var fields = { email: email.value, website: (f.querySelector('[name="website"]') || {}).value, sector: (f.querySelector('[name="sector"]') || {}).value };
          btn.disabled = true; say('Sending...');
          return post(F, base, kind, ed, payload(kind, fields)).then(function (r) {
            var o = outcome(kind, r.status, r.body);
            if (o.field) { say(''); st.hidden = true; fieldError(o.text); return; }
            var text = o.text;
            if (o.ok && extra && extra.checked) {
              if (!flags.newsletter) text += ' The newsletter is coming soon, so we did not sign you up for it.';
              else return post(F, base, 'newsletter', ed, payload('newsletter', fields)).then(function (n) {
                say(text + (n.status === 202 ? ' We have also sent a newsletter confirmation link.' : ' The newsletter sign-up did not go through; please try again from the footer.'));
              });
            }
            say(text, !o.ok);
            if (o.ok && typeof window !== 'undefined' && window.GJTrack) window.GJTrack(kind === 'alerts' ? 'alert_signup' : 'newsletter_signup', { src_page: window.location.pathname });
          }).catch(function () { say('Not sent: network error. Please try again.', true); }).then(function () { btn.disabled = false; });
        });
      });
    });
    return flagsP;
  }
  /* ---- on-site application form (email-mode jobs, eye review r2 N1/N2). It posts to the SAME API base as the
     live data: '' = the board's own /api/apply (production), else the Worker origin with ?site= (staging, where the
     Pages origin has no /api/apply and answered 405). Multipart, so no preflight; credentials omitted cross-origin.
     referrerPolicy keeps the Origin header real on a same-origin Worker page (no-referrer sends "Origin: null"). */
  var APPLY_FIELD = {
    name: 'Please enter your name.',
    email: 'Please enter a valid email address, like name@example.com.',
    phone: 'Please enter a phone number using digits, spaces, brackets or +.',
    cover_note: 'Please keep the cover note under 5,000 characters.',
    consent: 'Please tick the box so we can send your application to the advertiser.',
  };
  function applyUrl(body, ed, action) {
    var base = apiBase(body);
    if (base === null || (ed !== 'ie' && ed !== 'uk')) return action || '/api/apply'; /* static demo: the form's own action */
    return base ? base + '/api/apply?site=' + ed : '/api/apply';
  }
  /* Worker answer -> {ok, text, fields: {name: message}} */
  function applyOutcome(status, body) {
    var e = body && body.error;
    if (status === 201) return { ok: true, text: 'Application received. Thank you: it is on its way to the advertiser.' };
    if (status === 200 && body && body.status === 'already_received') return { ok: true, text: 'Application received. We already had it, so nothing was sent twice.' };
    if (status === 400 && e === 'invalid_input' && body && Array.isArray(body.fields) && body.fields.length) {
      var f = {};
      body.fields.forEach(function (k) { f[k] = APPLY_FIELD[k] || 'Please check this field.'; });
      return { ok: false, text: 'Please correct the highlighted fields.', fields: f };
    }
    if (e === 'delivery_failed') return { ok: false, text: 'We could not send your application just now. Please try again in a few minutes.' };
    if (e === 'cv_too_large') return { ok: false, text: 'The CV is too large.', fields: { cv: 'Please choose a file under 5 MB.' } };
    if (e === 'cv_type' || e === 'cv_empty') return { ok: false, text: 'The CV could not be read.', fields: { cv: 'Please choose a PDF or Word file.' } };
    if (e === 'apply_externally') return { ok: false, text: 'This role takes applications on the employer\'s own site.' };
    if (e === 'job_not_found' || status === 410) return { ok: false, text: 'This role is no longer open for applications.' };
    if (status === 429) return { ok: false, text: 'Too many applications from this connection. Please try again in 10 minutes.' };
    if (e === 'too_fast' || e === 'form_expired' || e === 'invalid_ts') return { ok: false, text: 'Please reload the page and send the form again.' };
    if (status === 503) return { ok: false, text: 'We could not take applications for this role just now. Please try again later.' };
    return { ok: false, text: 'Not sent (' + (e || 'error ' + status) + '). Please try again.' };
  }
  /* Client-side checks before posting (same rules the Worker applies). -> {field: message} */
  function applyCheck(f) {
    var out = {}, v = function (n) { var el = f.querySelector('[name="' + n + '"]'); return el ? el : null; };
    var name = v('name'), email = v('email'), consent = v('consent');
    if (name && !String(name.value || '').trim()) out.name = APPLY_FIELD.name;
    if (email && (!String(email.value || '').trim() || (email.checkValidity && !email.checkValidity()))) out.email = APPLY_FIELD.email;
    if (consent && !consent.checked) out.consent = APPLY_FIELD.consent;
    return out;
  }
  function initApply(doc, fetchFn, FD) {
    var forms = Array.prototype.slice.call(doc.querySelectorAll('form[data-apply-form]'));
    var F = fetchFn || (typeof fetch === 'function' ? fetch.bind(window) : null);
    FD = FD || (typeof FormData !== 'undefined' ? FormData : null);
    if (!forms.length || !F || !FD) return null; /* no fetch: the native POST to the action */
    var body = doc.body, ed = body.getAttribute('data-edition'), base = apiBase(body);
    forms.forEach(function (f) {
      var st = f.querySelector('[data-apply-status]'), btn = f.querySelector('[type="submit"]');
      f.noValidate = true; /* our own per-field messages replace the browser bubbles */
      function say(text, isErr) { st.textContent = text; st.classList.toggle('is-err', !!isErr); st.hidden = false; }
      function clear() {
        Array.prototype.forEach.call(f.querySelectorAll('[data-apply-err]'), function (p) {
          p.textContent = ''; p.hidden = true;
          var el = f.querySelector('[name="' + p.getAttribute('data-apply-err') + '"]'); if (el) el.removeAttribute('aria-invalid');
        });
      }
      function mark(fields) {
        var first = null;
        Object.keys(fields).forEach(function (k) {
          var p = f.querySelector('[data-apply-err="' + k + '"]'), el = f.querySelector('[name="' + k + '"]');
          if (p) { p.textContent = fields[k]; p.hidden = false; }
          if (el) { el.setAttribute('aria-invalid', 'true'); if (!first) first = el; }
        });
        if (first && first.focus) first.focus();
      }
      /* eye r3 R3-3: after a successful send the form is cleared (the render stamp kept), the button says it is
         done, and the sticky bar no longer offers "Apply now" for this job. */
      function applied() {
        var ts = f.querySelector('[data-apply-ts]'), keep = ts ? ts.value : '';
        if (typeof f.reset === 'function') f.reset();
        if (ts) ts.value = keep;
        f.setAttribute('data-applied', '');
        btn.disabled = true; btn.textContent = 'Application sent';
        Array.prototype.forEach.call(doc.querySelectorAll('[data-sticky-apply] a[data-apply]') || [], function (a) {
          a.textContent = 'Application sent'; a.setAttribute('aria-label', 'Application sent: see the confirmation');
          a.classList.add('is-done');
        });
        var bar = doc.querySelector ? doc.querySelector('[data-sticky-apply]') : null; if (bar) bar.classList.add('is-applied');
      }
      f.addEventListener('submit', function (e) {
        e.preventDefault();
        clear();
        var bad = applyCheck(f);
        if (Object.keys(bad).length) { mark(bad); say('Please correct the highlighted fields.', true); return; }
        var url = applyUrl(body, ed, f.getAttribute('action'));
        btn.disabled = true; say('Sending...');
        return F(url, { method: 'POST', body: new FD(f), credentials: base ? 'omit' : 'same-origin', referrerPolicy: 'strict-origin-when-cross-origin' })
          .then(function (r) { return r.json().catch(function () { return {}; }).then(function (d) { return applyOutcome(r.status, d); }); })
          .then(function (o) { if (o.fields) mark(o.fields); say(o.text, !o.ok); if (o.ok) applied(); })
          .catch(function () { say('Not sent: network error. Please try again.', true); })
          .then(function () { if (!f.hasAttribute('data-applied')) btn.disabled = false; });
      });
    });
    return forms.length;
  }
  if (typeof document !== 'undefined') {
    var boot = function () { initForms(document); initApply(document); };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
  }
  return { initForms: initForms, initApply: initApply, applyUrl: applyUrl, applyOutcome: applyOutcome, applyCheck: applyCheck, apiBase: apiBase, loadJobs: loadJobs, merge: merge, board: board, outcome: outcome, payload: payload, post: post, cacheGet: cacheGet, cachePut: cachePut, TTL_MS: TTL_MS, MAX_PAGES: MAX_PAGES };
});
