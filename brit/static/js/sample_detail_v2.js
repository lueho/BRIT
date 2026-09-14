(function () {
  "use strict";

  const root = document.querySelector(".sdv2");
  if (!root) return;

  const actionRail = root.querySelector(".sdv2-rail");
  if (actionRail && "ResizeObserver" in window) {
    new ResizeObserver(() => {
      root.style.setProperty("--sdv2-rail-height", `${actionRail.offsetHeight}px`);
    }).observe(actionRail);
  }

  /* ---------- Keyboard navigation (invisible power-user affordances) ---------- */
  const groupCards = Array.from(document.querySelectorAll(".sdv2-group-card"));
  let groupCursor = -1;

  function focusGroup(idx) {
    if (!groupCards.length) return;
    idx = (idx + groupCards.length) % groupCards.length;
    groupCursor = idx;
    const card = groupCards[idx];
    card.scrollIntoView({ behavior: "smooth", block: "start" });
    card.classList.add("is-focused");
    setTimeout(() => card.classList.remove("is-focused"), 900);
  }

  function isEditableTarget(target) {
    if (!target) return false;
    const tag = target.tagName;
    return (
      tag === "INPUT" ||
      tag === "TEXTAREA" ||
      tag === "SELECT" ||
      target.isContentEditable
    );
  }

  document.addEventListener("keydown", (e) => {
    if (isEditableTarget(e.target)) return;
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    switch (e.key) {
      case "j":
        e.preventDefault();
        focusGroup(groupCursor + 1);
        break;
      case "k":
        e.preventDefault();
        focusGroup(groupCursor - 1);
        break;
      case "e": {
        const canEdit = root.dataset.canEdit === "1";
        const editingNow = root.dataset.editEnabled === "1";
        if (!canEdit) return;
        const url = new URL(window.location.href);
        url.searchParams.delete("experience");
        if (editingNow) url.searchParams.delete("mode");
        else url.searchParams.set("mode", "edit");
        window.location.href = url.toString();
        break;
      }
      default:
        break;
    }
  });

  /* ---------- Raw-measurement disclosure controls ---------- */
  document.querySelectorAll("[data-sdv2-raws-toggle]").forEach((trigger) => {
    trigger.addEventListener("click", () => {
      const shouldOpen = trigger.dataset.sdv2RawsToggle === "expand";
      document.querySelectorAll("details.sdv2-raws").forEach((details) => {
        details.open = shouldOpen;
      });
    });
  });

  /* ---------- Export affordances ---------- */
  let compositionsById = {};
  try {
    const raw = document.getElementById("sdv2-export-data");
    if (raw) {
      const parsed = JSON.parse(raw.textContent);
      (parsed || []).forEach((c) => {
        if (c && c.group != null) compositionsById[String(c.group)] = c;
      });
    }
  } catch (err) {
    console.warn("sdv2 export data parse failed", err);
  }

  function flashButton(btn, label) {
    const original = btn.innerHTML;
    btn.innerHTML = label;
    btn.classList.add("sdv2-flashed");
    setTimeout(() => {
      btn.innerHTML = original;
      btn.classList.remove("sdv2-flashed");
    }, 900);
  }

  async function copyToClipboard(text) {
    try {
      if (navigator.clipboard) {
        await navigator.clipboard.writeText(text);
        return true;
      }
    } catch (err) {
      console.warn("sdv2 clipboard failed", err);
    }
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.className = "sdv2-clipboard-textarea";
    document.body.appendChild(ta);
    ta.select();
    try {
      document.execCommand("copy");
      return true;
    } catch (err) {
      return false;
    } finally {
      document.body.removeChild(ta);
    }
  }

  function compositionToCsv(composition) {
    const header = "component,share_percent";
    const rows = (composition.shares || []).map((s) => {
      const pct = (s.average || 0) * 100;
      return `${JSON.stringify(s.component_name || "")},${pct.toFixed(2)}`;
    });
    return [header, ...rows].join("\n");
  }

  document.querySelectorAll("[data-sdv2-export]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const mode = btn.dataset.sdv2Export;
      const groupId = btn.dataset.sdv2Group;
      const composition = compositionsById[String(groupId)];
      if (!composition) return;
      let payload;
      if (mode === "json") payload = JSON.stringify(composition, null, 2);
      else if (mode === "csv") payload = compositionToCsv(composition);
      else return;
      const ok = await copyToClipboard(payload);
      flashButton(btn, ok ? "Copied ✓" : "Copy failed");
    });
  });

  document.querySelectorAll("[data-sdv2-permalink]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const hash = btn.dataset.sdv2Permalink || "";
      const url = window.location.origin + window.location.pathname +
        window.location.search + hash;
      const ok = await copyToClipboard(url);
      flashButton(btn, ok ? "Copied ✓" : "Copy failed");
    });
  });

  document.querySelectorAll("[data-sdv2-cite]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const base = btn.dataset.sdv2Cite || "";
      const url = window.location.href;
      const citation = `${base}. Retrieved from ${url}`;
      const ok = await copyToClipboard(citation);
      flashButton(btn, ok ? "Copied ✓" : "Copy failed");
    });
  });

  /* ---------- Sample export (whole sample → XLSX) ---------- */
  function setExportBusy(trigger, label) {
    if (!trigger) return;
    if (!trigger.dataset.originalHtml) {
      trigger.dataset.originalHtml = trigger.innerHTML;
    }
    trigger.disabled = true;
    trigger.setAttribute("aria-busy", "true");
    trigger.innerHTML = `<i class="fas fa-spinner fa-spin" aria-hidden="true"></i> <span class="sdv2-export-trigger-label">${label}</span>`;
  }

  function resetExportTrigger(trigger) {
    if (!trigger) return;
    if (trigger.dataset.originalHtml) {
      trigger.innerHTML = trigger.dataset.originalHtml;
      delete trigger.dataset.originalHtml;
    }
    trigger.disabled = false;
    trigger.removeAttribute("aria-busy");
  }

  function pollExportProgress(taskId, progressTemplate, trigger) {
    const url = progressTemplate.replace("TASK_ID", encodeURIComponent(taskId));
    fetch(url, { credentials: "same-origin" })
      .then((resp) => resp.json())
      .then((data) => {
        if (!data) throw new Error("empty response");
        if (data.state === "SUCCESS") {
          const details = data.details || {};
          setExportBusy(trigger, "Done");
          if (details.url) {
            window.location.href = details.url;
          }
          setTimeout(() => resetExportTrigger(trigger), 2000);
        } else if (data.state === "FAILURE") {
          resetExportTrigger(trigger);
          const msg = (data.details && data.details.error) || "Export failed";
          alert(msg);
        } else if (data.state === "PROGRESS") {
          const pct = (data.details && data.details.percent) || 0;
          setExportBusy(trigger, `${pct}%`);
          setTimeout(() => pollExportProgress(taskId, progressTemplate, trigger), 600);
        } else {
          // PENDING / STARTED / unknown – keep polling.
          setExportBusy(trigger, "Queued");
          setTimeout(() => pollExportProgress(taskId, progressTemplate, trigger), 800);
        }
      })
      .catch((err) => {
        console.warn("sdv2 export progress failed", err);
        resetExportTrigger(trigger);
        alert("Export polling failed. See console for details.");
      });
  }

  function startSampleExport(trigger) {
    const exportUrl = trigger && trigger.dataset.exportUrl;
    const progressTemplate = trigger && trigger.dataset.progressTemplate;
    if (!exportUrl || !progressTemplate) return;
    setExportBusy(trigger, "Starting…");
    fetch(exportUrl, { credentials: "same-origin" })
      .then((resp) => {
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        return resp.json();
      })
      .then((data) => {
        if (!data || !data.task_id) throw new Error("No task_id in response");
        pollExportProgress(data.task_id, progressTemplate, trigger);
      })
      .catch((err) => {
        console.warn("sdv2 export start failed", err);
        resetExportTrigger(trigger);
        alert("Failed to start export. See console for details.");
      });
  }

  document.querySelectorAll("[data-sdv2-export-sample]").forEach((el) => {
    el.addEventListener("click", (e) => {
      e.preventDefault();
      startSampleExport(el);
    });
  });

  /* ---------- Smooth anchor focus highlight ---------- */
  const style = document.createElement("style");
  style.textContent = `
    .sdv2-group-card.is-focused {
      box-shadow: 0 0 0 3px var(--sdv2-accent-derived-soft), var(--sdv2-shadow);
      transition: box-shadow 0.2s ease;
    }
    .sdv2-flashed { pointer-events: none; opacity: 0.85; }
  `;
  document.head.appendChild(style);
})();
