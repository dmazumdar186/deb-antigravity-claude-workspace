'use strict';
(function (root, factory) {
if (typeof module === 'object' && module.exports) module.exports = factory();
else root.GJ = factory();
})(typeof self !== 'undefined' ? self : this, function () {
var STOP = 'a an and are as at be by for from in is it of on or the to with we you your our will this that'.split(' ');
var STOPSET = {};
STOP.forEach(function (w) { STOPSET[w] = 1; });
function norm(s) {
return String(s == null ? '' : s).toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
}
function tokens(s) {
return norm(s).split(/[^a-z0-9+]+/).filter(function (w) { return w.length > 1 && !STOPSET[w]; });
}
function esc(s) {
return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
});
}
var SYM = { EUR: '€', GBP: '£', USD: '$' };
function money(n, cur) {
if (n == null || isNaN(n)) return '';
var s = SYM[cur] || '';
if (n >= 1000) return s + (n % 1000 === 0 ? (n / 1000) + 'k' : (Math.round(n / 100) / 10) + 'k');
return s + n;
}
function salaryLabel(j) {
if (j.sal_min == null && j.sal_max == null) return '';
var per = { year: '', month: '/mo', hour: '/hr', day: '/day', week: '/wk' }[j.period || 'year'] || '';
if (j.sal_min != null && j.sal_max != null && j.sal_max !== j.sal_min) {
return money(j.sal_min, j.cur) + '–' + money(j.sal_max, j.cur).replace(/^[^\d]+/, '') + per;
}
var v = j.sal_min != null ? j.sal_min : j.sal_max;
return (j.sal_max == null && j.sal_min != null && j.sal_text && /up to/i.test(j.sal_text) ? 'up to ' : '') + money(v, j.cur) + per;
}
var MULT = { year: 1, month: 12, week: 52, day: 230, hour: 1950 };
function annual(j) {
var m = MULT[j.period || 'year'];
if (!m || (j.sal_min == null && j.sal_max == null)) return null;
var lo = j.sal_min != null ? j.sal_min * m : j.sal_max * m;
var hi = j.sal_max != null ? j.sal_max * m : lo;
if (lo < 8000 || hi > 400000) return null;
return { lo: lo, hi: hi, mid: (lo + hi) / 2 };
}
function median(a) {
if (!a.length) return null;
var s = a.slice().sort(function (x, y) { return x - y; });
var m = s.length >> 1;
return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}
function histogram(values, edges) {
var out = edges.map(function (e, i) {
var hi = edges[i + 1];
return { lo: e, hi: hi, label: hi == null ? money(e, '') + '+' : money(e, '') + '–' + money(hi, ''), n: 0 };
});
values.forEach(function (v) {
for (var i = out.length - 1; i >= 0; i--) if (v >= out[i].lo) { out[i].n++; break; }
});
return out;
}
function daysAgo(iso, now) {
if (!iso) return null;
var t = Date.parse(iso);
if (isNaN(t)) return null;
return Math.max(0, Math.floor(((now || Date.now()) - t) / 864e5));
}
function ago(iso, now) {
var d = daysAgo(iso, now);
if (d == null) return '';
return d === 0 ? 'Today' : d === 1 ? 'Yesterday' : d < 7 ? d + ' days ago' : d < 30 ? Math.round(d / 7) + ' wk ago' : Math.round(d / 30) + ' mo ago';
}
var KEYS = ['q', 'loc', 'sector', 'type', 'sal', 'sort', 'view'];
function parseState(qs) {
var st = {};
String(qs || '').replace(/^\?/, '').split('&').forEach(function (kv) {
if (!kv) return;
var i = kv.indexOf('='), k, v;
try {
k = decodeURIComponent(kv.slice(0, i < 0 ? kv.length : i).replace(/\+/g, ' '));
v = i < 0 ? '' : decodeURIComponent(kv.slice(i + 1).replace(/\+/g, ' '));
} catch (e) { return; }
if (KEYS.indexOf(k) >= 0) st[k] = v;
});
return st;
}
function jobUrl(jobsHref, href) {
return String(jobsHref || '').replace(/index\.html$/, '') + String(href || '');
}
function toQuery(st) {
var parts = [];
KEYS.forEach(function (k) {
var v = st[k];
if (v && !(k === 'sort' && v === 'newest') && !(k === 'view' && v === 'list')) parts.push(encodeURIComponent(k) + '=' + encodeURIComponent(v));
});
return parts.length ? '?' + parts.join('&') : '';
}
function haystack(j) {
return j._h || (j._h = norm([j.title, j.employer, j.location, (j.sectors || []).join(' '), j.type, j.summary].join(' ')));
}
function matchesQ(j, q) {
if (!q) return true;
var h = haystack(j), words = tokens(q);
if (!words.length) return h.indexOf(norm(q)) >= 0;
return words.every(function (w) { return h.indexOf(w) >= 0; });
}
function filterJobs(jobs, st) {
var loc = norm(st.loc), sec = norm(st.sector), typ = norm(st.type);
var out = jobs.filter(function (j) {
if (!matchesQ(j, st.q)) return false;
if (loc && !(norm(j.location).indexOf(loc) >= 0 || (j.regions || []).some(function (r) { return norm(r) === loc; }))) return false;
if (sec && !(j.sectors || []).some(function (s) { return norm(s) === sec; })) return false;
if (typ && norm(j.type) !== typ) return false;
if (st.sal && j.sal_min == null && j.sal_max == null) return false;
return true;
});
return sortJobs(out, st.sort);
}
function sortJobs(list, sort) {
var a = list.slice();
if (sort === 'salary') {
a.sort(function (x, y) {
var ax = annual(x), ay = annual(y);
return (ay ? ay.hi : -1) - (ax ? ax.hi : -1);
});
} else if (sort === 'az') {
a.sort(function (x, y) { return x.title.localeCompare(y.title); });
} else {
a.sort(function (x, y) { return (y.posted || '').localeCompare(x.posted || '') || x.title.localeCompare(y.title); });
}
return a;
}
function suggest(jobs, q, limit) {
var w = norm(q), out = [], seen = {};
if (!w) return out;
function add(kind, text, sub) {
var k = kind + ':' + norm(text);
if (seen[k] || out.length >= (limit || 8)) return;
seen[k] = 1;
out.push({ kind: kind, text: text, sub: sub || '' });
}
jobs.forEach(function (j) { if (norm(j.title).indexOf(w) >= 0) add('role', j.title, j.employer); });
var cnt = {};
jobs.forEach(function (j) {
(j.sectors || []).forEach(function (s) { if (norm(s).indexOf(w) >= 0) cnt['sector:' + s] = (cnt['sector:' + s] || 0) + 1; });
(j.regions || []).forEach(function (r) { if (norm(r).indexOf(w) >= 0) cnt['place:' + r] = (cnt['place:' + r] || 0) + 1; });
if (norm(j.employer).indexOf(w) >= 0) cnt['employer:' + j.employer] = (cnt['employer:' + j.employer] || 0) + 1;
});
Object.keys(cnt).sort(function (a, b) { return cnt[b] - cnt[a]; }).forEach(function (k) {
var i = k.indexOf(':');
add(k.slice(0, i), k.slice(i + 1), cnt[k] + ' roles');
});
return out;
}
function buildIndex(jobs) {
var df = {}, docs = jobs.map(function (j) {
var tf = {}, n = 0;
tokens([j.title, j.title, (j.sectors || []).join(' '), j.summary, j.text].join(' ')).forEach(function (w) { tf[w] = (tf[w] || 0) + 1; n++; });
Object.keys(tf).forEach(function (w) { df[w] = (df[w] || 0) + 1; });
return { tf: tf, n: n || 1 };
});
var N = jobs.length, idf = {};
Object.keys(df).forEach(function (w) { idf[w] = Math.log(1 + N / df[w]); });
return { docs: docs, idf: idf };
}
function smartMatch(query, jobs, idx, limit) {
var qt = {};
tokens(query).forEach(function (w) { qt[w] = (qt[w] || 0) + 1; });
var words = Object.keys(qt).filter(function (w) { return idx.idf[w]; });
var res = jobs.map(function (j, i) {
var d = idx.docs[i], score = 0, hits = [];
words.forEach(function (w) {
if (d.tf[w]) { var s = (d.tf[w] / d.n) * idx.idf[w] * Math.sqrt(qt[w]); score += s; hits.push({ w: w, s: s }); }
});
hits.sort(function (a, b) { return b.s - a.s; });
return { job: j, score: score, terms: hits.slice(0, 5).map(function (h) { return h.w; }) };
}).filter(function (r) { return r.score > 0; });
res.sort(function (a, b) { return b.score - a.score; });
return res.slice(0, limit || 5);
}
function scoreSectors(answers, questions, sectors) {
var score = {};
sectors.forEach(function (s) { score[s] = 0; });
questions.forEach(function (q, qi) {
var a = answers[qi];
if (a == null || !q.opts[a] || !q.opts[a].w) return;
var w = q.opts[a].w;
Object.keys(w).forEach(function (s) { if (s in score) score[s] += w[s] * (q.weight || 1); });
});
var max = Math.max.apply(null, sectors.map(function (s) { return score[s]; })) || 1;
return sectors.map(function (s) { return { sector: s, score: score[s], pct: Math.round(100 * score[s] / max) }; })
.sort(function (a, b) { return b.score - a.score || a.sector.localeCompare(b.sector); });
}
function encodeAnswers(a) { return a.map(function (v) { return v == null ? '' : v; }).join('.'); }
function decodeAnswers(s, n) {
var out = [];
String(s || '').split('.').forEach(function (v, i) { if (i < n) out[i] = v === '' ? null : Math.max(0, parseInt(v, 10) || 0); });
return out;
}
function treemap(items, w, h) {
var total = items.reduce(function (s, i) { return s + i.v; }, 0) || 1;
var rects = [], x = 0, y = 0, W = w, H = h, i = 0;
var sorted = items.slice().sort(function (a, b) { return b.v - a.v; });
while (i < sorted.length) {
var horiz = W >= H, row = [], sum = 0, best = Infinity;
while (i < sorted.length) {
var v = sorted[i].v * (W * H) / total, cand = row.concat([sorted[i]]), s2 = sum + v;
var side = horiz ? H : W, len = s2 / side, worst = 0;
cand.forEach(function (c) { var a = c.v * (W * H) / total, r = Math.max(len / (a / len), (a / len) / len); if (r > worst) worst = r; });
if (worst > best && row.length) break;
row = cand; sum = s2; best = worst; i++;
}
var len2 = sum / (horiz ? H : W), off = 0;
row.forEach(function (c) {
var a = c.v * (W * H) / total, e = a / len2;
rects.push(horiz ? { x: x, y: y + off, w: len2, h: e, item: c } : { x: x + off, y: y, w: e, h: len2, item: c });
off += e;
});
if (horiz) { x += len2; W -= len2; } else { y += len2; H -= len2; }
total -= row.reduce(function (s, c) { return s + c.v; }, 0);
if (total <= 0) break;
}
return rects;
}
function stem(w) {
if (w.length < 5) return w;
w = w.replace(/s$/, '');
return w.length > 4 ? w.replace(/(ist|ical|ing|er|e|y)$/, '') : w;
}
function stems(s) { return tokens(s).map(stem); }
function bigrams(list) {
var out = [];
for (var i = 0; i + 1 < list.length; i++) out.push(list[i] + '_' + list[i + 1]);
return out;
}
function fitIndex(jobs) {
var df = {}, docs = jobs.map(function (j) {
var tf = {}, n = 0;
function add(words, w) { words.forEach(function (x) { tf[x] = (tf[x] || 0) + w; n += w; }); }
var t = stems(j.title), sm = stems(j.summary);
add(t, 3); add(bigrams(t), 3);
add(stems((j.sectors || []).join(' ')), 2);
add(stems([j.employer, j.location, (j.regions || []).join(' ')].join(' ')), 1.5);
add(sm, 1); add(bigrams(sm), 1.2); add(stems(j.text), 0.6);
Object.keys(tf).forEach(function (w) { df[w] = (df[w] || 0) + 1; });
return { tf: tf, n: n || 1, sec: stems((j.sectors || []).join(' ')), place: stems([j.location, (j.regions || []).join(' ')].join(' ')) };
});
var N = jobs.length, idf = {};
Object.keys(df).forEach(function (w) { idf[w] = Math.log(1 + N / df[w]); });
return { docs: docs, idf: idf };
}
function fitMatch(query, jobs, idx, limit) {
var words = tokens(query), qs = words.map(stem), orig = {}, qt = {};
qs.forEach(function (s, i) { qt[s] = (qt[s] || 0) + 1; if (!orig[s]) orig[s] = words[i]; });
bigrams(qs).forEach(function (b) { qt[b] = (qt[b] || 0) + 1; orig[b] = b.replace('_', ' '); });
var keys = Object.keys(qt).filter(function (w) { return idx.idf[w]; });
var res = jobs.map(function (j, i) {
var d = idx.docs[i], score = 0, hits = [], boost = 1;
keys.forEach(function (w) {
if (d.tf[w]) { var s = (d.tf[w] / d.n) * idx.idf[w] * Math.sqrt(qt[w]); score += s; hits.push({ w: w, s: s }); }
});
if (!score) return null;
if (qs.some(function (s) { return d.sec.indexOf(s) >= 0; })) boost *= 1.25;
if (qs.some(function (s) { return d.place.indexOf(s) >= 0; })) boost *= 1.3;
hits.sort(function (a, b) { return b.s - a.s; });
var seen = {}, terms = [];
hits.forEach(function (h) { var o = orig[h.w]; if (o && !seen[o] && terms.length < 5) { seen[o] = 1; terms.push(o); } });
return { job: j, score: score * boost, terms: terms, stems: hits.map(function (h) { return h.w; }).filter(function (w) { return w.indexOf('_') < 0; }) };
}).filter(Boolean);
res.sort(function (a, b) { return b.score - a.score || a.job.title.localeCompare(b.job.title); });
return res.slice(0, limit || 6);
}
function salaryPosition(hits, jobs) {
var all = jobs.map(annual).filter(Boolean).map(function (a) { return a.mid; }).sort(function (a, b) { return a - b; });
var mine = hits.map(function (h) { return annual(h.job || h); }).filter(Boolean);
function pct(v) { var k = 0; while (k < all.length && all[k] < v) k++; return all.length ? Math.round(100 * k / all.length) : 0; }
var out = { n: hits.length, disclosed: mine.length, share: hits.length ? Math.round(100 * mine.length / hits.length) : 0,
board: { n: all.length, min: all[0] || 0, max: all[all.length - 1] || 0, median: median(all) || 0 }, lo: null, hi: null, plo: null, phi: null };
if (mine.length) {
out.lo = Math.min.apply(null, mine.map(function (a) { return a.lo; }));
out.hi = Math.max.apply(null, mine.map(function (a) { return a.hi; }));
out.plo = pct(out.lo); out.phi = pct(out.hi);
}
return out;
}
function encodeFit(q) {
var seen = {}, out = [];
tokens(q).forEach(function (w) { if (!seen[w] && out.length < 14) { seen[w] = 1; out.push(w); } });
return encodeURIComponent(out.join('.'));
}
function decodeFit(hash) {
var m = /(?:^|[#&])fit=([^&]*)/.exec(String(hash || ''));
if (!m) return '';
try { return decodeURIComponent(m[1]).split('.').filter(Boolean).join(' '); } catch (e) { return ''; }
}
function easeOutQuart(t) { t = t < 0 ? 0 : t > 1 ? 1 : t; return 1 - Math.pow(1 - t, 4); }
function filmScrub(p, last) {
p = p < 0 ? 0 : p > 1 ? 1 : p;
var t = Math.min(last, (p / 0.92) * last), s = Math.floor(Math.min(t, last - 0.001)), f = t - s;
var g = Math.min(1, Math.max(0, (f - 0.15) / 0.7));
var fills = [];
for (var i = 0; i <= last; i++) fills.push(Math.min(1, Math.max(0, t - i)));
return { t: t, s: s, f: f, g: g, show: f < 0.5 ? s : Math.min(last, s + 1), fills: fills };
}
function countAt(from, to, u) { return Math.round(from + (to - from) * easeOutQuart(u)); }
return {
stem: stem, fitIndex: fitIndex, fitMatch: fitMatch, salaryPosition: salaryPosition, encodeFit: encodeFit, decodeFit: decodeFit,
easeOutQuart: easeOutQuart, filmScrub: filmScrub, countAt: countAt,
norm: norm, tokens: tokens, esc: esc, money: money, salaryLabel: salaryLabel, annual: annual, median: median,
histogram: histogram, daysAgo: daysAgo, ago: ago, parseState: parseState, toQuery: toQuery, filterJobs: filterJobs,
sortJobs: sortJobs, suggest: suggest, buildIndex: buildIndex, smartMatch: smartMatch, scoreSectors: scoreSectors,
encodeAnswers: encodeAnswers, decodeAnswers: decodeAnswers, treemap: treemap, haystack: haystack, jobUrl: jobUrl
};
});
