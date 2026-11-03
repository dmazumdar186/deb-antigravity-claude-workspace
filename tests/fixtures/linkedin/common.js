// Mimics the parts of a LinkedIn profile the send script reads: top card buttons, More menu,
// invitation dialog, "Invitation sent" alert, header flip to Pending, Escape closing overlays.
function el(html) { const t = document.createElement('template'); t.innerHTML = html.trim(); return t.content.firstChild; }
function inviteFlow(name, mode) {
  if (mode === 'none') return;
  if (mode === 'email') {
    document.body.appendChild(el('<div role="dialog" aria-label="Connect"><p>To verify this member knows you, please enter their email to connect.</p><input type="email" aria-label="Email"><button disabled>Send</button></div>'));
    return;
  }
  const d = el('<div role="dialog" aria-labelledby="dh"><h2 id="dh">Add a note to your invitation?</h2><button id="note">Add a note</button><button id="send" aria-label="Send without a note">Send without a note</button></div>');
  document.body.appendChild(d);
  d.querySelector('#note').onclick = () => { window.noteClicked = true; };
  d.querySelector('#send').onclick = () => {
    d.remove();
    if (mode === 'limit') {
      document.body.appendChild(el('<div role="dialog"><p>You’ve reached the weekly invitation limit</p><button>Got it</button></div>'));
      return;
    }
    window.sendClicked = true;
    document.body.appendChild(el('<div role="alert">Invitation sent to ' + name.split(' ')[0] + '.</div>'));
    const p = el('<button aria-label="Pending, click to withdraw invitation sent to ' + name + '">Pending</button>');
    const c = document.querySelector('#header-connect');
    if (c) c.replaceWith(p); else document.querySelector('#actions').appendChild(p);
  };
}
function wire(name, mode) {
  document.querySelectorAll('[data-connect]').forEach(b => b.onclick = () => { window.connectClicked = (window.connectClicked || 0) + 1; inviteFlow(name, mode); });
  const more = document.querySelector('#more');
  if (more) more.onclick = () => { document.querySelector('#menu').hidden = false; };
  document.querySelectorAll('[data-other]').forEach(b => b.onclick = () => { window.otherClicked = true; });
}
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    document.querySelectorAll('[role=dialog]').forEach(x => x.remove());
    document.querySelectorAll('[role=menu]').forEach(m => m.hidden = true);
  }
});
