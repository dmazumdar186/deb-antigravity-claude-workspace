'use strict';
(function initSite() {
var M = window.GaiaMotion;
var reduce = window.matchMedia('(prefers-reduced-motion: reduce)');
var desktop = window.matchMedia('(min-width: 800px)');
var hdr = document.querySelector('[data-header]');
var stack = document.querySelector('[data-stack]');
var cards = stack ? Array.prototype.slice.call(stack.querySelectorAll('[data-card]')) : [];
var stackSteps = stack ? Array.prototype.slice.call(stack.querySelectorAll('[data-stack-step]')) : [];
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
if (stackFrozen) {
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
(function freezeStack() {
var hook = /[?&]stack=([0-9.]+)/.exec(window.location.search || '');
if (!hook || !stack || !cards.length || !M) return;
if (!desktop.matches || reduce.matches) return;
window.removeEventListener('scroll', onScroll);
stackFrozen = true;
paintStack(Math.min(1, Math.max(0, parseFloat(hook[1]) || 0)));
}());
var toggle = document.querySelector('[data-menu-toggle]');
var menu = document.querySelector('[data-menu]');
if (toggle && menu) {
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
obs.disconnect();
}, 20000);
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
if (window.console) window.console.warn('Copy unavailable:', err);
}
document.body.removeChild(ta);
}
});
}());
