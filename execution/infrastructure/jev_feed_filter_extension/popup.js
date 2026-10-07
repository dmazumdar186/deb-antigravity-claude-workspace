const $ = (id) => document.getElementById(id);
chrome.storage.local.get(["slopEnabled", "unclutterEnabled"], (s) => {
  $("slop").checked = s.slopEnabled !== false;
  $("unclutter").checked = !!s.unclutterEnabled;
});
$("slop").addEventListener("change", (e) => chrome.storage.local.set({ slopEnabled: e.target.checked }));
$("unclutter").addEventListener("change", (e) => chrome.storage.local.set({ unclutterEnabled: e.target.checked }));
chrome.runtime.sendMessage({ type: "stats" }, (st) => {
  if (!st) return;
  $("checked").textContent = st.checked;
  $("folded").textContent = st.folded;
  $("cost").textContent = Number(st.cost).toFixed(5);
});
$("undo").addEventListener("click", async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (tab) chrome.tabs.sendMessage(tab.id, { type: "undoAll" }, (r) => {
    $("undo").textContent = r ? `Restored ${r.restored}` : "Nothing to undo";
  });
});
