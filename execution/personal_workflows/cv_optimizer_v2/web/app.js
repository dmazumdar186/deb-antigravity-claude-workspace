// CV Optimizer v2 — frontend logic.
// NO secrets in this file. NO API keys. The Pages Function at
// functions/api/optimize.js handles auth server-side.

(function () {
  "use strict";

  // pdf.js worker thread — MANDATORY for v4+; without this, getDocument()
  // throws "Setting up fake worker failed" or silently fails in v3.
  if (typeof pdfjsLib !== "undefined") {
    pdfjsLib.GlobalWorkerOptions.workerSrc = "./lib/pdf.worker.min.js";
  }

  const $ = (id) => document.getElementById(id);
  const jdUrlInput = $("jd-url");
  const jdTextInput = $("jd-text");
  const cvFileInput = $("cv-file");
  const cvStatus = $("cv-status");
  const optimizeBtn = $("optimize-btn");
  const errorBanner = $("error-banner");
  const statusBanner = $("status-banner");
  const previewCard = $("preview-card");
  const previewIframe = $("preview-iframe");
  const printBtn = $("print-btn");

  let cvText = "";
  let cvSpec = null;

  function updateButton() {
    const hasCv = cvText.length > 50;
    const hasJd = jdUrlInput.value.trim().length > 0 || jdTextInput.value.trim().length > 50;
    optimizeBtn.disabled = !(hasCv && hasJd);
  }

  function showError(msg) {
    errorBanner.textContent = msg;
    errorBanner.classList.remove("hidden");
  }
  function clearError() {
    errorBanner.classList.add("hidden");
  }
  function showStatus(msg) {
    statusBanner.textContent = msg;
    statusBanner.classList.remove("hidden");
  }
  function clearStatus() {
    statusBanner.classList.add("hidden");
  }

  cvFileInput.addEventListener("change", async (e) => {
    const file = e.target.files[0];
    if (!file) {
      cvText = "";
      cvStatus.textContent = "No file selected.";
      updateButton();
      return;
    }

    cvStatus.textContent = `Parsing ${file.name} ...`;
    clearError();
    try {
      const buf = await file.arrayBuffer();
      const pdf = await pdfjsLib.getDocument({ data: buf }).promise;
      const pages = [];
      for (let i = 1; i <= pdf.numPages; i++) {
        const page = await pdf.getPage(i);
        const content = await page.getTextContent();
        const text = content.items.map((it) => it.str).join(" ");
        pages.push(text);
      }
      cvText = pages.join("\n\n");
      cvStatus.textContent = `Parsed: ${file.name} (${cvText.length} chars, ${pdf.numPages} pages).`;
    } catch (err) {
      cvText = "";
      cvStatus.textContent = "Failed to parse PDF — try a different file.";
      showError("PDF parse error: " + (err.message || String(err)));
    }
    updateButton();
  });

  jdUrlInput.addEventListener("input", updateButton);
  jdTextInput.addEventListener("input", updateButton);

  optimizeBtn.addEventListener("click", async () => {
    clearError();
    optimizeBtn.disabled = true;
    showStatus("Optimizing with Sonnet 4.6 ... this typically takes 25-50 seconds.");

    try {
      const resp = await fetch("/api/optimize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          cv_text: cvText,
          jd_url: jdUrlInput.value.trim() || undefined,
          jd_text: jdTextInput.value.trim() || undefined,
        }),
      });

      if (resp.status === 400) {
        const body = await resp.json().catch(() => ({}));
        if (body.error === "jd_scrape_failed") {
          showError(
            "Could not read the JD URL (probably login-walled or thin content). " +
              "Paste the job description text in the textarea instead, then click Optimize again."
          );
          jdTextInput.focus();
          jdTextInput.scrollIntoView({ behavior: "smooth", block: "center" });
        } else {
          showError(`Request rejected (400): ${body.error || "validation failed"}.`);
        }
        clearStatus();
        updateButton();
        return;
      }

      if (resp.status === 429) {
        const body = await resp.json().catch(() => ({}));
        showError(`Rate limited. Retry in ${body.retry_after_seconds || 60}s.`);
        clearStatus();
        updateButton();
        return;
      }

      if (!resp.ok) {
        showError(`Worker error (HTTP ${resp.status}). Try again or paste the JD as text.`);
        clearStatus();
        updateButton();
        return;
      }

      cvSpec = await resp.json();
      await renderPreview(cvSpec);
      clearStatus();
    } catch (err) {
      showError("Network error: " + (err.message || String(err)));
      clearStatus();
    }
    updateButton();
  });

  async function renderPreview(spec) {
    const tplResp = await fetch("./cv-template.html");
    let html = await tplResp.text();
    // Simple slot substitution: {{field}} → spec.field; arrays handled below.
    html = html.replace(/\{\{name\}\}/g, esc(spec.name || ""));
    html = html.replace(/\{\{title\}\}/g, esc(spec.title || ""));
    html = html.replace(/\{\{ats_score\}\}/g, esc(String(spec.ats_score ?? "")));
    html = html.replace(/\{\{language_detected\}\}/g, esc(spec.language_detected || ""));
    html = html.replace(/\{\{summary\}\}/g, esc(spec.summary || ""));
    html = html.replace(/\{\{summary_kpis\}\}/g, esc(spec.summary_kpis || ""));
    html = html.replace(/\{\{contact_email\}\}/g, esc(spec.contact?.email || ""));
    html = html.replace(/\{\{contact_phone\}\}/g, esc(spec.contact?.phone || ""));
    html = html.replace(/\{\{contact_location\}\}/g, esc(spec.contact?.location || ""));
    html = html.replace(/\{\{contact_linkedin\}\}/g, esc(spec.contact?.linkedin || ""));
    html = html.replace(/\{\{contact_github\}\}/g, esc(spec.contact?.github || ""));

    const expHtml = (spec.experience || []).map((e) => `
      <div class="exp">
        <div class="exp-role">${esc(e.role)}</div>
        <div class="exp-company">${esc(e.company_line)}</div>
        <ul class="exp-bullets">${(e.bullets || []).map((b) => `<li>${esc(b)}</li>`).join("")}</ul>
      </div>
    `).join("");
    html = html.replace("{{experience_block}}", expHtml);

    const skillsHtml = (spec.skills || []).map((s) =>
      `<div class="skill-row"><span class="skill-cat">${esc(s.category)}</span><span class="skill-val">${esc(s.value)}</span></div>`
    ).join("");
    html = html.replace("{{skills_block}}", skillsHtml);

    const eduHtml = (spec.education || []).map((e) =>
      `<div class="edu"><div class="edu-degree">${esc(e.degree)}</div><div class="edu-inst">${esc(e.institution_line)}</div></div>`
    ).join("");
    html = html.replace("{{education_block}}", eduHtml);

    const langsHtml = (spec.languages || []).join(" · ");
    html = html.replace("{{languages}}", esc(langsHtml));

    const certsHtml = (spec.certifications || []).map((c) => `<li>${esc(c)}</li>`).join("");
    html = html.replace("{{certifications_block}}", certsHtml ? `<ul>${certsHtml}</ul>` : "");

    const projsHtml = (spec.projects || []).map((p) => `<li>${esc(p)}</li>`).join("");
    html = html.replace("{{projects_block}}", projsHtml ? `<ul>${projsHtml}</ul>` : "");

    const recsHtml = (spec.recommendations || []).map((r) => `<li>${esc(r)}</li>`).join("");
    html = html.replace("{{recommendations_block}}", recsHtml);

    previewIframe.srcdoc = html;
    previewCard.classList.remove("hidden");
    previewCard.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function esc(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  printBtn.addEventListener("click", () => {
    if (previewIframe.contentWindow) {
      previewIframe.contentWindow.focus();
      previewIframe.contentWindow.print();
    } else {
      window.print();
    }
  });
})();
