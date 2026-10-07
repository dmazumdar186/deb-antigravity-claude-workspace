const $ = (id) => document.getElementById(id);
chrome.storage.local.get(["openrouterKey", "slopEnabled", "unclutterEnabled", "threshold"], (s) => {
  $("key").value = s.openrouterKey || "";
  $("slop").checked = s.slopEnabled !== false;
  $("unclutter").checked = !!s.unclutterEnabled;
  const t = typeof s.threshold === "number" ? s.threshold : 0.7;
  $("threshold").value = t; $("tval").textContent = t.toFixed(2);
});
$("threshold").addEventListener("input", (e) => { $("tval").textContent = Number(e.target.value).toFixed(2); });
$("save").addEventListener("click", () => {
  chrome.storage.local.set({
    openrouterKey: $("key").value.trim(),
    slopEnabled: $("slop").checked,
    unclutterEnabled: $("unclutter").checked,
    threshold: Number($("threshold").value)
  }, () => { $("status").textContent = "Saved."; });
});
