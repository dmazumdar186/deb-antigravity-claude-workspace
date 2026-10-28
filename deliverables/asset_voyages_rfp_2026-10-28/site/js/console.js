/* console.js — mock-up buttons explain themselves instead of looking disabled. */
(function () {
  'use strict';
  var t = null, timer = 0;
  document.addEventListener('click', function (e) {
    var b = e.target.closest ? e.target.closest('[data-mock]') : null;
    if (!b) return;
    if (!t) { t = document.createElement('p'); t.className = 'mtoast'; t.setAttribute('role', 'status'); document.body.appendChild(t); }
    t.textContent = 'Maquette : « ' + b.textContent.trim() + ' » sera actif dans la vraie Console.';
    t.hidden = false; clearTimeout(timer); timer = setTimeout(function () { t.hidden = true; }, 2600);
  });
}());
