(() => {
  const CANDIDATES = '[id*=cookie],[class*=cookie],[class*=banner],[class*=promo],aside,[aria-label*=advert],iframe';
  const AD_SRC = /doubleclick|googlesyndication|adservice|adsystem|taboola|outbrain|\/ads?\//i;
  const byId = new Map();
  let nextId = 0;

  function candidates() {
    const set = new Set();
    for (const el of document.querySelectorAll(CANDIDATES)) {
      if (el.tagName === "IFRAME" && !AD_SRC.test(el.src || "")) continue;
      set.add(el);
    }
    for (const el of document.body ? document.body.querySelectorAll("*") : []) {
      const pos = getComputedStyle(el).position;
      if (pos === "fixed" || pos === "sticky") set.add(el);
    }
    return [...set].filter((el) => !el.dataset.jevUcId && el.offsetParent !== null || getComputedStyle(el).position === "fixed").slice(0, 40);
  }

  function describe(el) {
    const text = (el.innerText || "").replace(/\s+/g, " ").trim().slice(0, 200);
    return JSON.stringify({
      tag: el.tagName.toLowerCase(), id: el.id || "", class: String(el.className || "").slice(0, 120),
      text, position: getComputedStyle(el).position, src: el.src ? String(el.src).slice(0, 120) : undefined
    });
  }

  function run(threshold) {
    const items = [];
    for (const el of candidates()) {
      if (el.dataset.jevUcId) continue;
      const id = "u" + nextId++;
      el.dataset.jevUcId = id;
      byId.set(id, el);
      items.push({ id, text: describe(el) });
    }
    if (!items.length) return;
    chrome.runtime.sendMessage({ type: "classify", mode: "unclutter", items }, (probs) => {
      if (chrome.runtime.lastError || !probs) return;
      let n = 0;
      for (const [id, p] of Object.entries(probs)) {
        const el = byId.get(id);
        if (!el || p < threshold) continue;
        el.dataset.jevHidden = el.style.display || "__empty__";
        el.style.setProperty("display", "none", "important");
        n++;
      }
      if (n) chrome.runtime.sendMessage({ type: "folded", n });
    });
  }

  function undoAll() {
    let n = 0;
    for (const el of document.querySelectorAll("[data-jev-hidden]")) {
      const prev = el.dataset.jevHidden;
      el.style.removeProperty("display");
      if (prev !== "__empty__") el.style.display = prev;
      delete el.dataset.jevHidden;
      n++;
    }
    for (const el of document.querySelectorAll('[data-jev-folded="1"]')) {
      el.style.display = "";
      delete el.dataset.jevFolded;
      const bar = el.previousElementSibling;
      if (bar && bar.className === "jev-fold-bar") bar.remove();
      n++;
    }
    return n;
  }

  chrome.runtime.onMessage.addListener((msg, _s, reply) => {
    if (msg && msg.type === "undoAll") reply({ restored: undoAll() });
    return false;
  });

  chrome.storage.local.get(["unclutterEnabled", "threshold"], (s) => {
    s = s || {};
    if (!s.unclutterEnabled) return; // gated by toggle, default off
    const t = typeof s.threshold === "number" ? s.threshold : 0.7;
    run(t);
    setTimeout(() => run(t), 2500); // late popups
  });
})();
