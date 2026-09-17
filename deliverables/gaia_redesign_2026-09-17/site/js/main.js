'use strict';
(function initSite() {
var M = window.GaiaMotion;
var reduce = window.matchMedia('(prefers-reduced-motion: reduce)');
var desktop = window.matchMedia('(min-width: 800px)');
var hdr = document.querySelector('[data-header]');
var stack = document.querySelector('[data-stack]');
var cards = stack ? Array.prototype.slice.call(stack.querySelectorAll('[data-card]')) : [];
if (stack) stack.style.setProperty('--stack-span', String(cards.length));
var pending = false;
function update() {
pending = false;
var vh = window.innerHeight;
if (hdr) {
var range = Math.max(document.documentElement.scrollHeight - vh, 1);
hdr.classList.toggle('is-scrolled', window.scrollY > 48);
hdr.style.setProperty('--page-progress', String(Math.min(1, Math.max(0, window.scrollY / range))));
}
if (M && stack && cards.length && desktop.matches && !reduce.matches) {
var p = M.sectionProgress(stack.getBoundingClientRect(), vh);
stack.style.setProperty('--stack-progress', p.toFixed(3));
for (var i = 0; i < cards.length; i += 1) {
var s = M.stackCardState(p, i, cards.length);
var el = cards[i];
el.style.setProperty('--card-y', s.yPercent.toFixed(2) + '%');
el.style.setProperty('--card-rot', s.rotationDeg.toFixed(2) + 'deg');
el.style.setProperty('--card-scale', s.scale.toFixed(3));
el.style.setProperty('--card-opacity', s.opacity.toFixed(3));
el.style.zIndex = String(s.zIndex);
el.classList.toggle('is-front', s.isFront);
el.setAttribute('aria-hidden', s.opacity < 0.08 ? 'true' : 'false');
}
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
(function freezeStack() {
var hook = /[?&]stack=([0-9.]+)/.exec(window.location.search || '');
if (!hook || !stack || !cards.length || !M) return;
if (!desktop.matches || reduce.matches) return;
var p = Math.min(1, Math.max(0, parseFloat(hook[1]) || 0));
window.removeEventListener('scroll', onScroll);
stack.style.setProperty('--stack-progress', p.toFixed(3));
cards.forEach(function (el, i) {
var st = M.stackCardState(p, i, cards.length);
el.style.setProperty('--card-y', st.yPercent.toFixed(2) + '%');
el.style.setProperty('--card-rot', st.rotationDeg.toFixed(2) + 'deg');
el.style.setProperty('--card-scale', st.scale.toFixed(3));
el.style.setProperty('--card-opacity', st.opacity.toFixed(3));
el.style.zIndex = String(st.zIndex);
el.classList.toggle('is-front', st.isFront);
});
}());
var toggle = document.querySelector('[data-menu-toggle]');
var menu = document.querySelector('[data-menu]');
var main = document.querySelector('main');
if (toggle && menu) {
var setMenu = function (open) {
toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
menu.classList.toggle('is-open', open);
menu.inert = !open;
document.body.style.overflow = open ? 'hidden' : '';
if (main) main.inert = open;
if (open) {
var first = menu.querySelector('a, button');
if (first) first.focus();
} else {
toggle.focus();
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
window.setTimeout(function () {
items.forEach(function (el) { el.classList.add('is-visible'); });
}, 4000);
}
}
function compose(form) {
var lines = [];
var fields = form.querySelectorAll('input, select, textarea');
Array.prototype.forEach.call(fields, function (f) {
if (!f.name || f.type === 'submit') return;
if (f.type === 'radio' && !f.checked) return;
var value = (f.value || '').trim();
if (!value) return;
var label = f.dataset.label || (form.querySelector('label[for="' + f.id + '"]') || {}).textContent || f.name;
lines.push(String(label).replace(/\s+/g, ' ').trim() + ': ' + value);
});
return lines.join('\n');
}
Array.prototype.forEach.call(document.querySelectorAll('[data-compose]'), function (form) {
var out = document.getElementById(form.dataset.compose);
if (!out) return;
var pre = out.querySelector('pre');
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
mail.href = 'mailto:' + address
+ '?subject=' + encodeURIComponent(form.dataset.subject || 'Website enquiry')
+ '&body=' + encodeURIComponent(text);
mail.hidden = false;
} else {
mail.hidden = true;
}
}
out.setAttribute('tabindex', '-1');
out.focus({ preventScroll: false });
});
if (copy) {
copy.addEventListener('click', function () {
var text = pre.textContent;
var done = function () {
var span = copy.querySelector('.btn__t') || copy;
var was = span.textContent;
span.textContent = 'Copied';
window.setTimeout(function () { span.textContent = was; }, 2200);
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
if (window.console) window.console.warn('Copy unavailable:', err);
}
document.body.removeChild(ta);
}
});
}());
