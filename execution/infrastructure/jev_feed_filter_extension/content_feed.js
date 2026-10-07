(() => {
  const SELECTOR = 'article[data-testid="tweet"], div.feed-shared-update-v2';
  const seen = new WeakSet();
  const byId = new Map();
  let pending = [];
  let timer = null;
  let nextId = 0;
  let settings = { slopEnabled: true, threshold: 0.7 };

  function loadSettings() {
    return new Promise((res) => {
      try {
        chrome.storage.local.get(["slopEnabled", "threshold"], (s) => {
          s = s || {};
          if (typeof s.slopEnabled === "boolean") settings.slopEnabled = s.slopEnabled;
          if (typeof s.threshold === "number") settings.threshold = s.threshold;
          res();
        });
      } catch (_) { res(); }
    });
  }

  function textOf(el) {
    return (el.innerText || el.textContent || "").replace(/\s+/g, " ").trim().slice(0, 600);
  }

  function fold(el, p) {
    if (el.dataset.jevFolded === "1") return;
    const bar = document.createElement("div");
    bar.className = "jev-fold-bar";
    bar.style.cssText = "font:13px sans-serif;color:#666;padding:6px 12px;border:1px dashed #bbb;margin:4px 0;cursor:pointer";
    bar.textContent = `Folded by Jev (${p.toFixed(2)}) - show`;
    bar.addEventListener("click", () => {
      const hidden = el.style.display === "none";
      el.style.display = hidden ? "" : "none";
      bar.textContent = `Folded by Jev (${p.toFixed(2)}) - ${hidden ? "hide" : "show"}`;
    });
    el.parentNode.insertBefore(bar, el);
    el.dataset.jevFolded = "1";
    el.style.display = "none";
  }

  function flush() {
    timer = null;
    const batch = pending.splice(0, pending.length);
    if (!batch.length) return;
    try {
      chrome.runtime.sendMessage({ type: "classify", mode: "slop", items: batch }, (probs) => {
        if (chrome.runtime.lastError || !probs) return; // fail-open
        let n = 0;
        for (const [id, p] of Object.entries(probs)) {
          const el = byId.get(id);
          if (el && typeof p === "number" && p >= settings.threshold) { fold(el, p); n++; }
          if (el) el.dataset.jevScore = String(p);
        }
        if (n) chrome.runtime.sendMessage({ type: "folded", n });
      });
    } catch (_) { /* fail-open */ }
  }

  function scan(root) {
    if (!settings.slopEnabled) return;
    const els = root.querySelectorAll ? root.querySelectorAll(SELECTOR) : [];
    const texts = new Set(pending.map((x) => x.text));
    for (const el of els) {
      if (seen.has(el)) continue;
      seen.add(el);
      const text = textOf(el);
      if (text.length < 20 || texts.has(text)) continue;
      texts.add(text);
      const id = "p" + nextId++;
      el.dataset.jevId = id;
      byId.set(id, el);
      pending.push({ id, text });
    }
    if (pending.length && !timer) timer = setTimeout(flush, 300);
  }

  loadSettings().then(() => {
    scan(document);
    new MutationObserver(() => scan(document)).observe(document.documentElement, { childList: true, subtree: true });
  });
})();
