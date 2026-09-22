'use strict';
/* Green Career Compass: seven questions, one per screen, deterministic
   scoring to three sectors with live roles. Answers live in the URL hash so a
   result is shareable; back/forward and keyboard work throughout. */
(function () {
  var G = window.GJ, doc = document, host = doc.querySelector('[data-compass]');
  if (!host) return;
  var data = JSON.parse(doc.querySelector('#gj-data').textContent), jobs = data.jobs;
  var SEC = data.sectors.map(function (s) { return s.name; });
  var S = function () { var o = {}; for (var i = 0; i < arguments.length; i += 2) o[arguments[i]] = arguments[i + 1]; return o; };
  var W = 'Wind energy', SO = 'Solar energy', RE = 'Renewable energy & storage', WA = 'Water & flood', WS = 'Waste & circular economy', EC = 'Ecology & conservation', EN = 'Environmental science & consulting', SU = 'Sustainability & net zero', BE = 'Built environment & energy efficiency', NE = 'Energy networks & utilities', PO = 'Policy, planning & advisory';
  var regions = data.regions.slice(0, 5).map(function (r) { return r.name; });
  var Q = [
    { t: 'What would you most like your work to change?', weight: 3, opts: [
      { l: 'How we make power', w: S(W, 3, SO, 3, RE, 3, NE, 2) }, { l: 'How we use water and handle floods', w: S(WA, 4, EN, 1) },
      { l: 'What happens to what we throw away', w: S(WS, 4, SU, 1) }, { l: 'How much nature we keep', w: S(EC, 4, EN, 2) },
      { l: 'How buildings and cities perform', w: S(BE, 4, NE, 1, SU, 1) }, { l: 'How organisations plan and report', w: S(SU, 3, PO, 3, EN, 1) }] },
    { t: 'Which of these is your strongest suit?', weight: 2, opts: [
      { l: 'Engineering and technical design', w: S(W, 2, SO, 2, RE, 2, WA, 2, NE, 2, BE, 1) }, { l: 'Science and fieldwork', w: S(EC, 3, EN, 3, WA, 1) },
      { l: 'Data, modelling and analysis', w: S(SU, 2, EN, 2, NE, 1, WA, 1) }, { l: 'Running projects and people', w: S(RE, 2, BE, 2, WS, 2, W, 1, SO, 1) },
      { l: 'Policy, commercial and writing', w: S(PO, 3, SU, 2, WS, 1) }] },
    { t: 'Where do you do your best work?', weight: 1, opts: [
      { l: 'Outdoors and on site', w: S(EC, 2, W, 1, SO, 1, WA, 1, WS, 1) }, { l: 'At a desk, deep in the detail', w: S(SU, 2, PO, 2, EN, 1, NE, 1) },
      { l: 'A mix of both', w: S(EN, 1, BE, 1, RE, 1, WA, 1) }, { l: 'Wherever there is a good connection', w: S(SU, 1, PO, 1) }] },
    { t: 'Where would you like to be based?', weight: 0, opts: regions.map(function (r) { return { l: r, region: r }; }).concat([{ l: 'Anywhere' }]) },
    { t: 'What is the lowest salary you would consider?', weight: 0, opts: [{ l: 'Show me everything' }, { l: '30k and up', floor: 30000 }, { l: '45k and up', floor: 45000 }, { l: '60k and up', floor: 60000 }] },
    { t: 'What working pattern suits you?', weight: 0, opts: [{ l: 'Permanent' , type: 'Permanent' }, { l: 'Contract or interim', type: 'Contract' }, { l: 'Either' }] },
    { t: 'Where are you in your career?', weight: 0, opts: [{ l: 'Starting out', stage: 'junior' }, { l: 'Mid-career', stage: 'mid' }, { l: 'Senior or leading teams', stage: 'senior' }] }
  ];
  var answers = G.decodeAnswers(window.location.hash.replace(/^#a=/, ''), Q.length), step = firstOpen();
  function firstOpen() { for (var i = 0; i < Q.length; i++) if (answers[i] == null) return i; return Q.length; }
  function pushHash() { history.replaceState(null, '', '#a=' + G.encodeAnswers(answers)); }
  function stageOk(j, stage) {
    var t = G.norm(j.title), sen = /senior|lead|head|principal|director|manager|chief/.test(t), jun = /graduate|junior|assistant|trainee|intern|apprentice|entry/.test(t);
    return stage === 'senior' ? sen : stage === 'junior' ? !sen : !jun;
  }
  function roles(sector) {
    var o = Q.map(function (q, i) { return q.opts[answers[i]] || {}; });
    var region = o[3].region, floor = o[4].floor, type = o[5].type, stage = o[6].stage;
    var pool = jobs.filter(function (j) { return j.sectors.indexOf(sector) >= 0; });
    var tries = [
      function (j) { return (!region || j.regions.indexOf(region) >= 0) && (!floor || (G.annual(j) && G.annual(j).hi >= floor)) && (!type || j.type === type) && (!stage || stageOk(j, stage)); },
      function (j) { return (!region || j.regions.indexOf(region) >= 0) && (!floor || !G.annual(j) || G.annual(j).hi >= floor) && (!type || j.type === type); },
      function (j) { return (!region || j.regions.indexOf(region) >= 0); },
      function () { return true; }
    ];
    for (var i = 0; i < tries.length; i++) { var r = pool.filter(tries[i]); if (r.length) return { list: G.sortJobs(r, 'newest').slice(0, 3), relaxed: i }; }
    return { list: [], relaxed: 3 };
  }
  function render() {
    var pct = Math.round(100 * Math.min(step, Q.length) / Q.length);
    if (step >= Q.length) return results();
    var q = Q[step];
    host.innerHTML = '<div class="prog" aria-hidden="true"><i style="width:' + pct + '%"></i></div><div class="q fade-in" role="group" aria-labelledby="qh"><p class="step">Question ' + (step + 1) + ' of ' + Q.length + '</p><h2 id="qh">' + G.esc(q.t) + '</h2><div class="opts">' +
      q.opts.map(function (o, i) { return '<button type="button" class="opt" data-i="' + i + '" aria-pressed="' + (answers[step] === i) + '"><span class="k">' + String.fromCharCode(65 + i) + '</span>' + G.esc(o.l) + '</button>'; }).join('') +
      '</div><div class="q__nav"><button type="button" class="btn btn--ghost' + (step ? ' is-vis' : '') + '" data-back>← Back</button>' + (answers[step] != null ? '<button type="button" class="btn btn--fill" data-next>Next →</button>' : '<span class="muted" style="align-self:center;font-size:.9rem">Pick one to continue</span>') + '</div></div>';
    var h = host.querySelector('h2'); h.setAttribute('tabindex', '-1'); h.focus({ preventScroll: true });
  }
  function results() {
    var top = G.scoreSectors(answers, Q, SEC).slice(0, 3), url = window.location.href;
    host.innerHTML = '<div class="prog" aria-hidden="true"><i style="width:100%"></i></div><div class="res fade-in"><div class="res__top"><p class="step">Your compass</p><h2 id="qh">Three sectors that fit the way you answered</h2><p class="muted">Scored from your first three answers; the roles below also respect your location, salary floor, pattern and stage where the live data allows.</p></div>' +
      top.map(function (s) {
        var r = roles(s.sector), color = (data.sectors.filter(function (x) { return x.name === s.sector; })[0] || {}).color || '';
        return '<section class="res__sec"><h3><span><i class="tag" style="padding:0;border:0;margin-right:8px;width:12px;height:12px;border-radius:50%;background:' + G.esc(color) + '"></i>' + G.esc(s.sector) + '</span><span class="score">' + s.pct + '% match</span></h3><div class="barw"><i style="width:' + s.pct + '%"></i></div>' +
          (r.list.length ? '<div class="res__roles">' + r.list.map(function (j) { return '<a class="row" href="' + G.esc(j.href) + '" style="text-decoration:none"><div class="row__body"><h3>' + G.esc(j.title) + '</h3><div class="row__meta"><span>' + G.esc(j.employer) + '</span><span aria-hidden="true">·</span><span>' + G.esc(j.location) + '</span>' + (G.salaryLabel(j) ? '<span class="tag tag--sal">' + G.esc(G.salaryLabel(j)) + '</span>' : '') + '</div></div></a>'; }).join('') + '</div>' +
            (r.relaxed ? '<p class="muted" style="font-size:.85rem">' + ['', 'Loosened the career-stage filter to find these.', 'Loosened salary and pattern to find these.', 'No live match for your location; showing the latest in this sector.'][r.relaxed] + '</p>' : '')
            : '<p class="muted">No live roles in this sector this week — set an alert below.</p>') +
          '<a class="btn btn--sm btn--ghost" href="' + G.esc(data.jobsHref) + G.toQuery({ sector: s.sector }) + '">All ' + G.esc(s.sector) + ' roles →</a></section>';
      }).join('') +
      '<div class="res__actions"><button type="button" class="btn btn--fill" data-share>Share this result</button><button type="button" class="btn btn--ghost" data-restart>Start again</button></div><p class="muted" style="font-size:.85rem">Your result lives in this link: <code style="word-break:break-all">' + G.esc(url) + '</code></p></div>';
    var h = host.querySelector('h2'); h.setAttribute('tabindex', '-1'); h.focus({ preventScroll: true });
    host.querySelector('[data-share]').addEventListener('click', function () {
      if (navigator.share) navigator.share({ title: 'My Green Career Compass', url: url }).catch(function () { /* dismissed */ });
      else if (navigator.clipboard) navigator.clipboard.writeText(url).then(function () { window.GJsay('Link copied'); }, function () { window.GJsay('Copy failed'); });
    });
  }
  host.addEventListener('click', function (e) {
    var b = e.target.closest('[data-i],[data-back],[data-next],[data-restart]');
    if (!b) return;
    if (b.hasAttribute('data-i')) { answers[step] = +b.getAttribute('data-i'); pushHash(); step++; render(); }
    else if (b.hasAttribute('data-back')) { step = Math.max(0, step - 1); render(); }
    else if (b.hasAttribute('data-next')) { step++; render(); }
    else { answers = []; step = 0; history.replaceState(null, '', window.location.pathname); render(); }
  });
  window.addEventListener('hashchange', function () { answers = G.decodeAnswers(window.location.hash.replace(/^#a=/, ''), Q.length); step = firstOpen(); render(); });
  render();
})();
