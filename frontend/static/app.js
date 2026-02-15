const el = {
  syncBtn: document.getElementById("syncBtn"),
  safariFullBtn: document.getElementById("safariFullBtn"),
  liveBtn: document.getElementById("liveBtn"),
  powerBtn: document.getElementById("powerBtn"),
  reportBtn: document.getElementById("reportBtn"),
  reportRefreshBtn: document.getElementById("reportRefreshBtn"),
  downloadReportBtn: document.getElementById("downloadReportBtn"),
  permissionBtn: document.getElementById("permissionBtn"),
  clearHistoryBtn: document.getElementById("clearHistoryBtn"),
  captureWindowBtn: document.getElementById("captureWindowBtn"),
  deleteWindowBtn: document.getElementById("deleteWindowBtn"),
  clearWindowCaptureBtn: document.getElementById("clearWindowCaptureBtn"),
  clearSearchBtn: document.getElementById("clearSearchBtn"),
  searchBtn: document.getElementById("searchBtn"),
  searchInputPanel: document.getElementById("searchInputPanel"),
  permissionText: document.getElementById("permissionText"),
  captureHint: document.getElementById("captureHint"),
  startHour: document.getElementById("startHour"),
  endHour: document.getElementById("endHour"),
  totalEvents: document.getElementById("totalEvents"),
  latestEventAt: document.getElementById("latestEventAt"),
  freshnessStatus: document.getElementById("freshnessStatus"),
  lastSyncAt: document.getElementById("lastSyncAt"),
  lastSyncInserted: document.getElementById("lastSyncInserted"),
  activeDay: document.getElementById("activeDay"),
  syncedBrowsers: document.getElementById("syncedBrowsers"),
  lastAction: document.getElementById("lastAction"),
  modelName: document.getElementById("modelName"),
  searchMeta: document.getElementById("searchMeta"),
  resultCount: document.getElementById("resultCount"),
  resultsTitle: document.getElementById("resultsTitle"),
  historyList: document.getElementById("historyList"),
  similarResults: document.getElementById("similarResults"),
  similarCount: document.getElementById("similarCount"),
  domainList: document.getElementById("domainList"),
  domainHint: document.getElementById("domainHint"),
  reportSummary: document.getElementById("reportSummary"),
  reportDateBadge: document.getElementById("reportDateBadge"),
  reportEventsBadge: document.getElementById("reportEventsBadge"),
  importantHighlightList: document.getElementById("importantHighlightList"),
  keyFactList: document.getElementById("keyFactList"),
  highlightList: document.getElementById("highlightList"),
  patternList: document.getElementById("patternList"),
  timeInsightList: document.getElementById("timeInsightList"),
  categoryInsightList: document.getElementById("categoryInsightList"),
  recommendationList: document.getElementById("recommendationList"),
  riskList: document.getElementById("riskList"),
  intentSignalList: document.getElementById("intentSignalList"),
  focusGapList: document.getElementById("focusGapList"),
  actionPlanList: document.getElementById("actionPlanList"),
  methodologyList: document.getElementById("methodologyList"),
  deepResearchPaper: document.getElementById("deepResearchPaper"),
  reasoningTrace: document.getElementById("reasoningTrace"),
  reportPanel: document.getElementById("reportPanel"),
  windowCaptureList: document.getElementById("windowCaptureList"),
  windowCaptureCount: document.getElementById("windowCaptureCount"),
  savedStat: document.getElementById("savedStat"),
  homeCount: document.getElementById("homeCount"),
  savedCount: document.getElementById("savedCount"),
  browserAllCount: document.getElementById("browserAllCount"),
  browserSafariCount: document.getElementById("browserSafariCount"),
  browserBraveCount: document.getElementById("browserBraveCount"),
  browserChromeCount: document.getElementById("browserChromeCount"),
  toast: document.getElementById("toast"),
  viewButtons: Array.from(document.querySelectorAll(".view-btn")),
  navButtons: Array.from(document.querySelectorAll(".nav-item")),
  browserFilterButtons: Array.from(document.querySelectorAll(".browser-filter")),
  collectionFilterButtons: Array.from(document.querySelectorAll(".collection-filter")),
  pillButtons: Array.from(document.querySelectorAll(".filter-pill")),
};

const apiToken = typeof window !== "undefined" ? window.__WAVE_API_TOKEN__ || "" : "";
const SAVED_KEY = "wave_saved_events_v1";

const VIDEO_HINTS = ["youtube.com", "youtu.be", "netflix.com", "primevideo.com", "twitch.tv", "vimeo.com"];
const SHOPPING_HINTS = ["amazon.", "ebay.", "walmart.", "flipkart.", "aliexpress.", "etsy.", "shop", "cart"];
const SOCIAL_HINTS = ["facebook.com", "instagram.com", "x.com", "twitter.com", "reddit.com", "linkedin.com", "threads.net"];
const ARTICLE_HINTS = ["medium.com", "wikipedia.org", "news", "blog", "docs", "article", "substack.com"];

const state = {
  liveSyncEnabled: false,
  liveSyncTimer: null,
  syncInFlight: false,
  snapshot: null,
  searchMode: false,
  lastQuery: "",
  baseEvents: [],
  similarEvents: [],
  viewMode: "list",
  browserFilter: "all",
  collectionFilter: "all",
  nav: "home",
  byBrowser: {},
  saved: loadSavedStore(),
  windowCaptureEvents: [],
  currentReportDate: null,
  lastSyncInserted: 0,
  lastSyncAt: null,
};

function showToast(message, timeout = 2200) {
  el.toast.textContent = message;
  el.toast.classList.add("show");
  window.setTimeout(() => {
    el.toast.classList.remove("show");
  }, timeout);
}

async function api(path, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    "X-Wave-Token": apiToken,
    ...(options.headers || {}),
  };

  const response = await fetch(path, {
    headers,
    ...options,
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    const detail = Array.isArray(payload.detail)
      ? payload.detail.map((item) => item.msg || "Request error").join("; ")
      : payload.detail;
    throw new Error(detail || `Request failed: ${response.status}`);
  }

  return response.json();
}

function toDateTimeStamp(dateString) {
  const dt = new Date(dateString);
  return dt.toLocaleString([], {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: true,
  });
}

function toDateLabel(dateString) {
  const dt = new Date(dateString);
  if (Number.isNaN(dt.getTime())) {
    return "-";
  }
  return dt.toLocaleDateString([], {
    month: "short",
    day: "2-digit",
    year: "numeric",
  });
}

function formatHour(value) {
  const hour = Number(value);
  if (Number.isNaN(hour)) {
    return "";
  }
  const suffix = hour < 12 ? "AM" : "PM";
  const display = hour % 12 === 0 ? 12 : hour % 12;
  return `${display}:00 ${suffix}`;
}

function updateCaptureHint() {
  const start = Number(el.startHour.value);
  const end = Number(el.endHour.value);

  if (Number.isNaN(start) || Number.isNaN(end) || start === end) {
    el.captureHint.textContent = "All day (12:00 AM to 12:00 AM)";
    return;
  }

  el.captureHint.textContent = `${formatHour(start)} to ${formatHour(end)} (local)`;
}

function isInCaptureWindow(hour, startHour, endHour) {
  if (startHour === endHour) {
    return true;
  }
  if (startHour < endHour) {
    return startHour <= hour && hour < endHour;
  }
  return hour >= startHour || hour < endHour;
}

function getEventHour(event) {
  const asDate = new Date(event.visited_at);
  if (!Number.isNaN(asDate.getTime())) {
    return asDate.getHours();
  }
  const text = String(event.visited_at || "");
  const hourToken = text.slice(11, 13);
  const parsed = Number(hourToken);
  if (!Number.isNaN(parsed) && parsed >= 0 && parsed <= 23) {
    return parsed;
  }
  return null;
}

function filterByCaptureWindow(events, startHour, endHour) {
  return events.filter((event) => {
    const hour = getEventHour(event);
    return hour !== null && isInCaptureWindow(hour, startHour, endHour);
  });
}

function setupHourSelectors() {
  const startFrag = document.createDocumentFragment();
  const endFrag = document.createDocumentFragment();

  for (let hour = 0; hour < 24; hour += 1) {
    const label = formatHour(hour);

    const startOption = document.createElement("option");
    startOption.value = String(hour);
    startOption.textContent = label;

    const endOption = document.createElement("option");
    endOption.value = String(hour);
    endOption.textContent = label;

    startFrag.appendChild(startOption);
    endFrag.appendChild(endOption);
  }

  el.startHour.appendChild(startFrag);
  el.endHour.appendChild(endFrag);
  el.startHour.value = "0";
  el.endHour.value = "0";
  updateCaptureHint();
}

function getCaptureWindow() {
  return {
    captureStartHour: Number(el.startHour.value),
    captureEndHour: Number(el.endHour.value),
  };
}

function loadSavedStore() {
  try {
    const raw = window.localStorage.getItem(SAVED_KEY);
    if (!raw) {
      return {};
    }
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function persistSavedStore() {
  window.localStorage.setItem(SAVED_KEY, JSON.stringify(state.saved));
}

function eventKey(event) {
  return `${event.browser}|${event.url}|${event.visited_at}`;
}

function isSaved(event) {
  return Boolean(state.saved[eventKey(event)]);
}

function saveEvent(event) {
  const key = eventKey(event);
  state.saved[key] = {
    browser: event.browser,
    title: event.title,
    url: event.url,
    domain: event.domain,
    visited_at: event.visited_at,
  };
  persistSavedStore();
}

function unsaveEvent(event) {
  const key = eventKey(event);
  delete state.saved[key];
  persistSavedStore();
}

function browserRoot(label) {
  return String(label || "").split(":")[0].toLowerCase();
}

function browserLabel(label) {
  const source = String(label || "unknown");
  const [root, profile] = source.split(":");
  if (!profile) {
    return root;
  }
  return `${root} (${profile})`;
}

function classifyCollection(event) {
  const hay = `${event.domain} ${event.title} ${event.url}`.toLowerCase();

  if (VIDEO_HINTS.some((token) => hay.includes(token))) {
    return "videos";
  }
  if (SHOPPING_HINTS.some((token) => hay.includes(token))) {
    return "shopping";
  }
  if (SOCIAL_HINTS.some((token) => hay.includes(token))) {
    return "social";
  }
  if (ARTICLE_HINTS.some((token) => hay.includes(token))) {
    return "articles";
  }
  return "all";
}

function matchesFilters(event) {
  if (state.nav === "saved" && !isSaved(event)) {
    return false;
  }

  if (state.browserFilter !== "all" && browserRoot(event.browser) !== state.browserFilter) {
    return false;
  }

  if (state.collectionFilter !== "all" && classifyCollection(event) !== state.collectionFilter) {
    return false;
  }

  return true;
}

function emptyNode(text) {
  const node = document.createElement("p");
  node.className = "empty";
  node.textContent = text;
  return node;
}

function renderTextList(target, values, emptyText) {
  if (!target) {
    return;
  }

  target.innerHTML = "";
  if (!Array.isArray(values) || values.length === 0) {
    const li = document.createElement("li");
    li.textContent = emptyText;
    target.appendChild(li);
    return;
  }

  values.forEach((value) => {
    const text = String(value || "").trim();
    if (!text) {
      return;
    }
    const li = document.createElement("li");
    li.textContent = text;
    target.appendChild(li);
  });

  if (!target.children.length) {
    const li = document.createElement("li");
    li.textContent = emptyText;
    target.appendChild(li);
  }
}

function renderDomainList(domains) {
  el.domainList.innerHTML = "";
  el.domainHint.textContent = String(domains.length);

  if (!domains.length) {
    el.domainList.appendChild(emptyNode("No top domains yet."));
    return;
  }

  const fragment = document.createDocumentFragment();
  domains.forEach((item) => {
    const chip = document.createElement("span");
    chip.className = "chip";
    chip.textContent = `${item.domain} (${item.count})`;
    fragment.appendChild(chip);
  });

  el.domainList.appendChild(fragment);
}

function updateHealthStrip() {
  if (!el.freshnessStatus || !el.latestEventAt || !el.lastSyncAt || !el.lastSyncInserted || !el.activeDay) {
    return;
  }

  const timeline = Array.isArray(state.snapshot?.timeline) ? state.snapshot.timeline : [];
  const latest = timeline.length ? timeline[0].visited_at : null;
  el.activeDay.textContent = state.snapshot?.date ? toDateLabel(state.snapshot.date) : "-";
  el.lastSyncInserted.textContent = String(state.lastSyncInserted);
  el.lastSyncAt.textContent = state.lastSyncAt ? toDateTimeStamp(state.lastSyncAt) : "-";

  if (!latest) {
    el.latestEventAt.textContent = "Latest: -";
    el.freshnessStatus.textContent = "No Data";
    el.freshnessStatus.dataset.level = "none";
    return;
  }

  const latestDate = new Date(latest);
  if (Number.isNaN(latestDate.getTime())) {
    el.latestEventAt.textContent = "Latest: -";
    el.freshnessStatus.textContent = "No Data";
    el.freshnessStatus.dataset.level = "none";
    return;
  }
  const diffMinutes = Math.max(0, Math.round((Date.now() - latestDate.getTime()) / 60000));
  el.latestEventAt.textContent = `Latest: ${toDateTimeStamp(latest)}`;

  if (diffMinutes <= 5) {
    el.freshnessStatus.textContent = `Live (${diffMinutes}m)`;
    el.freshnessStatus.dataset.level = "live";
    return;
  }
  if (diffMinutes <= 30) {
    el.freshnessStatus.textContent = `Warm (${diffMinutes}m)`;
    el.freshnessStatus.dataset.level = "warm";
    return;
  }
  el.freshnessStatus.textContent = `Stale (${diffMinutes}m)`;
  el.freshnessStatus.dataset.level = "stale";
}

function renderWindowCapture() {
  if (!el.windowCaptureList || !el.windowCaptureCount) {
    return;
  }

  el.windowCaptureList.innerHTML = "";
  el.windowCaptureCount.textContent = String(state.windowCaptureEvents.length);

  if (!state.windowCaptureEvents.length) {
    el.windowCaptureList.appendChild(emptyNode("No captured entries for the selected time window."));
    return;
  }

  const fragment = document.createDocumentFragment();
  state.windowCaptureEvents.forEach((event) => {
    const item = document.createElement("article");
    item.className = "window-capture-item";

    const meta = document.createElement("div");
    meta.className = "window-capture-meta";

    const browser = document.createElement("span");
    browser.className = "window-capture-browser";
    browser.textContent = browserLabel(event.browser);

    const time = document.createElement("span");
    time.className = "window-capture-time";
    time.textContent = toDateTimeStamp(event.visited_at);

    meta.append(browser, time);

    const title = document.createElement("p");
    title.className = "window-capture-title";
    title.textContent = event.title || "Untitled";

    const link = document.createElement("a");
    link.className = "window-capture-url";
    link.href = event.url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = event.url;

    item.append(meta, title, link);
    fragment.appendChild(item);
  });

  el.windowCaptureList.appendChild(fragment);
}

function renderSimilar(events) {
  el.similarResults.innerHTML = "";
  el.similarCount.textContent = String(events.length);

  if (!events.length) {
    el.similarResults.appendChild(emptyNode("Similar links will appear here after search."));
    return;
  }

  const fragment = document.createDocumentFragment();
  events.slice(0, 8).forEach((event) => {
    const item = document.createElement("article");
    item.className = "similar-item";

    const link = document.createElement("a");
    link.href = event.url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = event.url;

    item.appendChild(link);
    fragment.appendChild(item);
  });

  el.similarResults.appendChild(fragment);
}

function renderReport(report) {
  el.modelName.textContent = `Model: ${report.model}`;
  state.currentReportDate = report.date || null;

  const details = report.details && typeof report.details === "object" ? report.details : {};
  const summary = String(report.summary || "No summary available.").trim();
  const narrative = String(details.narrative || "").trim();
  el.reportSummary.textContent = narrative.length > summary.length ? narrative : summary;
  el.reasoningTrace.textContent = report.reasoning_trace || "No reasoning trace captured.";
  if (el.reportDateBadge) {
    el.reportDateBadge.textContent = `Date: ${report.date || "-"}`;
  }
  if (el.reportEventsBadge) {
    el.reportEventsBadge.textContent = `Events: ${report.source_events || 0}`;
  }

  const importantHighlights = Array.isArray(details.important_highlights)
    ? details.important_highlights
    : [];
  const keyFacts = Array.isArray(details.key_facts) ? details.key_facts : [];

  renderTextList(
    el.importantHighlightList,
    importantHighlights.length ? importantHighlights : report.highlights,
    "No priority highlights available."
  );
  renderTextList(
    el.keyFactList,
    keyFacts.length ? keyFacts : [`Captured events: ${report.source_events || 0}`],
    "No key facts available."
  );
  renderTextList(el.highlightList, report.highlights, "No highlights.");
  renderTextList(el.patternList, details.behavior_patterns, "No clear patterns detected.");
  renderTextList(el.timeInsightList, details.time_insights, "No time insights available.");
  renderTextList(el.categoryInsightList, details.category_insights, "No category insights available.");
  renderTextList(el.riskList, report.risk_flags, "No critical risks detected.");
  renderTextList(el.recommendationList, details.recommendations, "No recommendations yet.");
  renderTextList(el.intentSignalList, details.intent_signals, "No strong intent signals available.");
  renderTextList(el.focusGapList, details.focus_gaps, "No major focus gaps detected.");
  renderTextList(el.actionPlanList, details.action_plan_7d, "No action plan generated.");
  renderTextList(el.methodologyList, details.methodology_notes, "No methodology notes.");
  if (el.deepResearchPaper) {
    el.deepResearchPaper.textContent = String(details.deep_research_paper || "No deep research paper available.");
  }
}

function resetReportUI() {
  state.currentReportDate = null;
  el.modelName.textContent = "Model: -";
  el.reportSummary.textContent = "Click AI Report to generate today's summary.";
  el.reasoningTrace.textContent = "No reasoning trace yet.";
  if (el.reportDateBadge) {
    el.reportDateBadge.textContent = "Date: -";
  }
  if (el.reportEventsBadge) {
    el.reportEventsBadge.textContent = "Events: 0";
  }
  renderTextList(el.importantHighlightList, [], "No priority highlights available.");
  renderTextList(el.keyFactList, [], "No key facts available.");
  renderTextList(el.highlightList, [], "No highlights.");
  renderTextList(el.patternList, [], "No clear patterns detected.");
  renderTextList(el.timeInsightList, [], "No time insights available.");
  renderTextList(el.categoryInsightList, [], "No category insights available.");
  renderTextList(el.riskList, [], "No critical risks detected.");
  renderTextList(el.recommendationList, [], "No recommendations yet.");
  renderTextList(el.intentSignalList, [], "No strong intent signals available.");
  renderTextList(el.focusGapList, [], "No major focus gaps detected.");
  renderTextList(el.actionPlanList, [], "No action plan generated.");
  renderTextList(el.methodologyList, [], "No methodology notes.");
  if (el.deepResearchPaper) {
    el.deepResearchPaper.textContent = "Generate AI report to produce a long, in-depth research paper for today.";
  }
}

function updateBadgeCounts(allEvents) {
  const counts = { all: allEvents.length, safari: 0, brave: 0, chrome: 0 };
  allEvents.forEach((event) => {
    const root = browserRoot(event.browser);
    if (root in counts) {
      counts[root] += 1;
    }
  });

  el.browserAllCount.textContent = String(counts.all);
  el.browserSafariCount.textContent = String(counts.safari);
  el.browserBraveCount.textContent = String(counts.brave);
  el.browserChromeCount.textContent = String(counts.chrome);
}

function updateSavedCounts() {
  const count = Object.keys(state.saved).length;
  el.savedCount.textContent = String(count);
  el.savedStat.textContent = String(count);
}

function setActive(buttons, key, value) {
  buttons.forEach((button) => {
    button.classList.toggle("active", button.dataset[key] === value);
  });
}

function applyAndRender() {
  const filtered = state.baseEvents.filter(matchesFilters);

  el.historyList.classList.remove("list", "grid", "compact");
  el.historyList.classList.add(state.viewMode);
  el.historyList.innerHTML = "";

  if (!filtered.length) {
    const message = state.nav === "saved" ? "No saved links yet." : "No history events for this filter.";
    el.historyList.appendChild(emptyNode(message));
  } else {
    const fragment = document.createDocumentFragment();

    filtered.forEach((event) => {
      const item = document.createElement("article");
      item.className = "history-item";

      const header = document.createElement("div");
      header.className = "item-header";

      const browser = document.createElement("span");
      const root = browserRoot(event.browser);
      browser.className = `browser-tag ${root}`;
      browser.textContent = browserLabel(event.browser);

      const time = document.createElement("span");
      time.className = "timestamp";
      time.textContent = toDateTimeStamp(event.visited_at);

      header.append(browser, time);

      const title = document.createElement("h3");
      title.className = "item-title";
      title.textContent = event.title || "Untitled";

      const url = document.createElement("a");
      url.className = "item-url";
      url.href = event.url;
      url.target = "_blank";
      url.rel = "noopener noreferrer";
      url.textContent = event.url;

      const actions = document.createElement("div");
      actions.className = "item-actions";

      const openBtn = document.createElement("button");
      openBtn.className = "action-btn";
      openBtn.type = "button";
      openBtn.innerHTML = "<span class=\"btn-icon\">↗</span><span>Open</span>";
      openBtn.addEventListener("click", () => {
        window.open(event.url, "_blank", "noopener,noreferrer");
      });

      const copyBtn = document.createElement("button");
      copyBtn.className = "action-btn";
      copyBtn.type = "button";
      copyBtn.innerHTML = "<span class=\"btn-icon\">⧉</span><span>Copy</span>";
      copyBtn.addEventListener("click", async () => {
        try {
          await navigator.clipboard.writeText(event.url);
          showToast("Link copied.");
        } catch {
          showToast("Could not copy link.");
        }
      });

      const saveBtn = document.createElement("button");
      saveBtn.className = `action-btn ${isSaved(event) ? "saved" : ""}`;
      saveBtn.type = "button";
      saveBtn.innerHTML = `<span class="btn-icon">★</span><span>${isSaved(event) ? "Saved" : "Save"}</span>`;
      saveBtn.addEventListener("click", () => {
        if (isSaved(event)) {
          unsaveEvent(event);
          showToast("Removed from saved.");
        } else {
          saveEvent(event);
          showToast("Saved.");
        }
        updateSavedCounts();
        applyAndRender();
      });

      actions.append(openBtn, copyBtn, saveBtn);
      item.append(header, title, url, actions);
      fragment.appendChild(item);
    });

    el.historyList.appendChild(fragment);
  }

  const label = state.searchMode ? `Search Results for "${state.lastQuery}"` : state.nav === "saved" ? "Saved Links" : "History Feed";
  el.resultsTitle.textContent = label;
  el.resultCount.textContent = `${filtered.length} result${filtered.length === 1 ? "" : "s"}`;
  el.homeCount.textContent = String(state.baseEvents.length);
  updateBadgeCounts(state.baseEvents);
  updateSavedCounts();
  renderSimilar(state.similarEvents.filter(matchesFilters));
}

async function loadSnapshot() {
  const snapshot = await api("/api/today");
  state.snapshot = snapshot;

  el.totalEvents.textContent = String(snapshot.total_events);
  renderDomainList(snapshot.top_domains);
  updateHealthStrip();

  if (!state.searchMode) {
    state.baseEvents = snapshot.timeline;
    state.similarEvents = [];
  }

  applyAndRender();
}

async function checkPermissions(silent = false) {
  try {
    const status = await api("/api/permissions");
    const safari = status.browsers.find((item) => item.browser === "safari");

    if (safari) {
      el.permissionText.textContent = `Safari: ${safari.status} | ${safari.message}`;
    }

    const ready = status.browsers.filter((item) => item.status === "ready").length;
    if (!state.syncInFlight) {
      el.syncedBrowsers.textContent = String(ready);
    }

    if (!silent && safari && safari.status !== "ready") {
      showToast("Safari permission is not fully ready.");
    }
  } catch (error) {
    if (!silent) {
      showToast(error.message || "Could not check permissions.");
    }
  }
}

async function runSync({
  silent = false,
  lookbackHours = 24,
  includeAllHistory = false,
  browsers = ["chrome", "brave", "safari"],
  label = "Syncing...",
  captureStartHour = null,
  captureEndHour = null,
} = {}) {
  if (state.syncInFlight) {
    return false;
  }

  state.syncInFlight = true;
  el.syncBtn.disabled = true;
  if (el.powerBtn) {
    el.powerBtn.disabled = true;
  }
  el.safariFullBtn.disabled = true;
  if (el.captureWindowBtn) {
    el.captureWindowBtn.disabled = true;
  }
  if (el.deleteWindowBtn) {
    el.deleteWindowBtn.disabled = true;
  }
  el.lastAction.textContent = label;

  try {
    const hasWindow =
      Number.isInteger(captureStartHour) &&
      Number.isInteger(captureEndHour) &&
      captureStartHour >= 0 &&
      captureStartHour <= 23 &&
      captureEndHour >= 0 &&
      captureEndHour <= 23;

    const body = {
      lookback_hours: lookbackHours,
      include_all_history: includeAllHistory,
      browsers,
    };
    if (hasWindow) {
      body.capture_start_hour = captureStartHour;
      body.capture_end_hour = captureEndHour;
    }

    const result = await api("/api/sync", {
      method: "POST",
      body: JSON.stringify(body),
    });

    state.byBrowser = result.by_browser;
    state.lastSyncInserted = Number(result.inserted || 0);
    state.lastSyncAt = new Date().toISOString();

    const syncedRoots = new Set(
      Object.entries(result.by_browser)
        .filter(([, count]) => count > 0)
        .map(([name]) => browserRoot(name))
    );

    el.syncedBrowsers.textContent = String(syncedRoots.size);
    el.lastAction.textContent = `Synced ${result.inserted} new events`;

    if (!silent) {
      if (Object.keys(result.errors).length) {
        showToast("Sync finished with warnings.");
      } else {
        showToast(`Sync complete: ${result.inserted} new events.`);
      }
    }

    await loadSnapshot();
    await checkPermissions(true);
    updateHealthStrip();
    return true;
  } catch (error) {
    el.lastAction.textContent = "Sync failed";
    showToast(error.message || "Sync failed.");
    return false;
  } finally {
    state.syncInFlight = false;
    el.syncBtn.disabled = false;
    if (el.powerBtn) {
      el.powerBtn.disabled = false;
    }
    el.safariFullBtn.disabled = false;
    if (el.captureWindowBtn) {
      el.captureWindowBtn.disabled = false;
    }
    if (el.deleteWindowBtn) {
      el.deleteWindowBtn.disabled = false;
    }
  }
}

function setLiveSync(enabled) {
  state.liveSyncEnabled = enabled;
  el.liveBtn.innerHTML = `<span class="btn-icon">◉</span>Live: ${enabled ? "On" : "Off"}`;

  if (state.liveSyncTimer) {
    window.clearInterval(state.liveSyncTimer);
    state.liveSyncTimer = null;
  }

  if (enabled) {
    state.liveSyncTimer = window.setInterval(() => {
      runSync({
        silent: true,
        lookbackHours: 1,
        includeAllHistory: false,
        browsers: ["chrome", "brave", "safari"],
        label: "Live syncing...",
      });
    }, 15000);
  }
}

function clearSearchInputs() {
  el.searchInputPanel.value = "";
}

async function runSearch() {
  const query = el.searchInputPanel.value.trim();

  if (query.length < 2) {
    state.searchMode = false;
    state.lastQuery = "";
    state.baseEvents = state.snapshot ? state.snapshot.timeline : [];
    state.similarEvents = [];
    el.searchMeta.textContent = "Showing today's timeline.";
    applyAndRender();
    return;
  }

  el.searchBtn.disabled = true;
  state.searchMode = true;
  state.lastQuery = query;
  el.lastAction.textContent = "Searching...";

  try {
    await runSync({
      silent: true,
      lookbackHours: 1,
      includeAllHistory: false,
      browsers: ["chrome", "brave", "safari"],
      label: "Syncing before search...",
    });

    const payload = await api(`/api/search?q=${encodeURIComponent(query)}&limit=60`);
    state.baseEvents = payload.results;
    state.similarEvents = payload.similar;
    el.searchMeta.textContent = `Found ${payload.total_matches} match${payload.total_matches === 1 ? "" : "es"} for "${payload.query}".`;
    el.lastAction.textContent = "Search complete";
    applyAndRender();
  } catch (error) {
    el.lastAction.textContent = "Search failed";
    showToast(error.message || "Search failed.");
  } finally {
    el.searchBtn.disabled = false;
  }
}

async function clearWaveData() {
  const confirmed = window.confirm("Delete all Wave app history and cached reports? This cannot be undone.");
  if (!confirmed) {
    return;
  }

  el.clearHistoryBtn.disabled = true;
  el.lastAction.textContent = "Deleting Wave data...";

  try {
    const payload = await api("/api/history/clear", {
      method: "POST",
      body: JSON.stringify({ include_reports: true }),
    });

    state.snapshot = null;
    state.searchMode = false;
    state.lastQuery = "";
    state.baseEvents = [];
    state.similarEvents = [];
    state.windowCaptureEvents = [];
    state.lastSyncInserted = 0;
    state.lastSyncAt = null;
    clearSearchInputs();

    el.totalEvents.textContent = "0";
    el.syncedBrowsers.textContent = "0";
    el.searchMeta.textContent = "History cleared.";
    el.lastAction.textContent = "Wave data deleted";
    renderDomainList([]);
    renderWindowCapture();
    resetReportUI();
    updateHealthStrip();
    applyAndRender();

    showToast(`Deleted ${payload.deleted_events} events and ${payload.deleted_reports} reports.`);
  } catch (error) {
    el.lastAction.textContent = "Delete failed";
    showToast(error.message || "Could not delete data.");
  } finally {
    el.clearHistoryBtn.disabled = false;
  }
}

async function captureSelectedWindow() {
  if (state.syncInFlight) {
    showToast("Sync already running.");
    return;
  }

  const { captureStartHour, captureEndHour } = getCaptureWindow();
  el.lastAction.textContent = "Capturing selected window...";

  try {
    const synced = await runSync({
      silent: true,
      lookbackHours: 24,
      includeAllHistory: false,
      browsers: ["chrome", "brave", "safari"],
      label: "Capturing selected window...",
    });
    if (!synced) {
      el.lastAction.textContent = "Capture failed";
      return;
    }

    const timeline = Array.isArray(state.snapshot?.timeline) ? state.snapshot.timeline : [];
    state.windowCaptureEvents = filterByCaptureWindow(timeline, captureStartHour, captureEndHour);
    renderWindowCapture();
    el.lastAction.textContent = "Capture window ready";
    showToast(`Captured ${state.windowCaptureEvents.length} event${state.windowCaptureEvents.length === 1 ? "" : "s"} in selected window.`);
  } catch (error) {
    el.lastAction.textContent = "Capture failed";
    showToast(error.message || "Could not capture selected window.");
  }
}

async function deleteSelectedWindowData() {
  if (state.syncInFlight) {
    showToast("Sync already running.");
    return;
  }

  const { captureStartHour, captureEndHour } = getCaptureWindow();
  const rangeLabel = `${formatHour(captureStartHour)} to ${formatHour(captureEndHour)}`;
  const confirmed = window.confirm(
    `Delete Wave history between ${rangeLabel} for ${state.snapshot?.date || "today"}?`
  );
  if (!confirmed) {
    return;
  }

  if (el.deleteWindowBtn) {
    el.deleteWindowBtn.disabled = true;
  }
  el.lastAction.textContent = "Deleting selected window...";

  try {
    const payload = await api("/api/history/window/delete", {
      method: "POST",
      body: JSON.stringify({
        date: state.snapshot?.date || null,
        capture_start_hour: captureStartHour,
        capture_end_hour: captureEndHour,
      }),
    });

    state.searchMode = false;
    state.lastQuery = "";
    clearSearchInputs();
    await loadSnapshot();

    const timeline = Array.isArray(state.snapshot?.timeline) ? state.snapshot.timeline : [];
    state.windowCaptureEvents = filterByCaptureWindow(timeline, captureStartHour, captureEndHour);
    renderWindowCapture();
    el.searchMeta.textContent = "Showing today's timeline.";
    el.lastAction.textContent = "Selected window deleted";
    showToast(
      `Deleted ${payload.deleted_events} event${payload.deleted_events === 1 ? "" : "s"} from selected window.`
    );
  } catch (error) {
    el.lastAction.textContent = "Window delete failed";
    showToast(error.message || "Could not delete selected window.");
  } finally {
    if (el.deleteWindowBtn) {
      el.deleteWindowBtn.disabled = false;
    }
  }
}

async function generateReport(forceRefresh = false, options = {}) {
  const { syncFirst = true } = options;
  el.reportBtn.disabled = true;
  if (el.reportRefreshBtn) {
    el.reportRefreshBtn.disabled = true;
  }
  el.lastAction.textContent = forceRefresh ? "Refreshing AI report..." : "Loading AI report...";

  try {
    if (syncFirst) {
      const synced = await runSync({
        silent: true,
        lookbackHours: 24,
        includeAllHistory: false,
        browsers: ["chrome", "brave", "safari"],
        label: "Syncing before AI report...",
      });
      if (!synced) {
        throw new Error("Sync failed before report generation.");
      }
    }

    const report = await api("/api/report", {
      method: "POST",
      body: JSON.stringify({ force_refresh: forceRefresh }),
    });
    renderReport(report);
    el.lastAction.textContent = "AI report ready";
    showToast(forceRefresh ? "Report refreshed." : "Report ready.");
  } catch (error) {
    el.lastAction.textContent = "AI report failed";
    showToast(error.message || "Could not generate report.");
  } finally {
    el.reportBtn.disabled = false;
    if (el.reportRefreshBtn) {
      el.reportRefreshBtn.disabled = false;
    }
  }
}

async function runPowerSync() {
  if (state.syncInFlight) {
    showToast("Sync already running.");
    return;
  }

  setNav("home");
  el.searchMeta.textContent = "Showing today's timeline.";
  el.lastAction.textContent = "Power sync running...";
  try {
    const synced = await runSync({
      silent: false,
      lookbackHours: 24,
      includeAllHistory: false,
      browsers: ["chrome", "brave", "safari"],
      label: "Power syncing everything...",
    });
    if (!synced) {
      return;
    }

    const { captureStartHour, captureEndHour } = getCaptureWindow();
    const timeline = Array.isArray(state.snapshot?.timeline) ? state.snapshot.timeline : [];
    state.windowCaptureEvents = filterByCaptureWindow(timeline, captureStartHour, captureEndHour);
    renderWindowCapture();
    await generateReport(false, { syncFirst: false });
    el.lastAction.textContent = "Power sync complete";
    showToast("Power sync complete.");
  } catch (error) {
    el.lastAction.textContent = "Power sync failed";
    showToast(error.message || "Power sync failed.");
  }
}

async function downloadReportPdf(forceRefresh = false) {
  if (el.downloadReportBtn) {
    el.downloadReportBtn.disabled = true;
  }
  el.lastAction.textContent = "Preparing PDF report...";

  try {
    const targetDate = state.currentReportDate || state.snapshot?.date || "";
    const params = new URLSearchParams();
    if (targetDate) {
      params.set("day", targetDate);
    }
    if (forceRefresh) {
      params.set("force_refresh", "true");
    }
    const url = `/api/report/pdf${params.toString() ? `?${params.toString()}` : ""}`;
    const response = await fetch(url, {
      headers: {
        "X-Wave-Token": apiToken,
      },
    });

    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      throw new Error(payload.detail || `PDF download failed: ${response.status}`);
    }

    const blob = await response.blob();
    if (!blob || blob.size === 0) {
      throw new Error("PDF file is empty.");
    }
    const disposition = response.headers.get("content-disposition") || "";
    const fileMatch = disposition.match(/filename=\"?([^\";]+)\"?/i);
    const filename = fileMatch ? fileMatch[1] : `wave-report-${targetDate || "today"}.pdf`;

    const downloadUrl = window.URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = downloadUrl;
    anchor.download = filename;
    const userAgent = navigator.userAgent || "";
    const isSafari = /safari/i.test(userAgent) && !/chrome|chromium|android/i.test(userAgent);
    if (isSafari) {
      anchor.target = "_blank";
      anchor.rel = "noopener noreferrer";
    }
    document.body.appendChild(anchor);
    anchor.click();
    window.setTimeout(() => {
      window.URL.revokeObjectURL(downloadUrl);
      anchor.remove();
    }, 45000);

    el.lastAction.textContent = "Report PDF downloaded";
    showToast(isSafari ? "PDF opened. Save/download from the opened tab." : "Detailed PDF report downloaded.");
  } catch (error) {
    el.lastAction.textContent = "PDF download failed";
    showToast(error.message || "Could not download PDF report.");
  } finally {
    if (el.downloadReportBtn) {
      el.downloadReportBtn.disabled = false;
    }
  }
}

async function loadCachedReport() {
  try {
    const report = await api("/api/report");
    renderReport(report);
  } catch {
    resetReportUI();
  }
}

function setViewMode(mode) {
  state.viewMode = mode;
  setActive(el.viewButtons, "view", mode);
  applyAndRender();
}

function setBrowserFilter(browser) {
  state.browserFilter = browser;
  setActive(el.browserFilterButtons, "browser", browser);
  applyAndRender();
}

function setCollectionFilter(collection) {
  state.collectionFilter = collection;
  setActive(el.collectionFilterButtons, "collection", collection);
  setActive(el.pillButtons, "collection", collection);
  applyAndRender();
}

function setNav(nav) {
  state.nav = nav;
  setActive(el.navButtons, "nav", nav);

  if (nav === "home") {
    state.searchMode = false;
    state.lastQuery = "";
    if (state.snapshot) {
      state.baseEvents = state.snapshot.timeline;
      state.similarEvents = [];
    }
    clearSearchInputs();
  }

  if (nav === "ai") {
    el.reportPanel.scrollIntoView({ behavior: "smooth", block: "start" });
    if (!state.currentReportDate) {
      generateReport(false);
    }
  }

  applyAndRender();
}

function attachListeners() {
  el.searchInputPanel.addEventListener("keydown", async (event) => {
    if (event.key === "Enter") {
      await runSearch();
    }
  });

  document.addEventListener("keydown", (event) => {
    const active = document.activeElement;
    const inInput = active && (active.tagName === "INPUT" || active.tagName === "TEXTAREA");
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      el.searchInputPanel.focus();
      el.searchInputPanel.select();
      return;
    }
    if (!inInput && event.key === "/") {
      event.preventDefault();
      el.searchInputPanel.focus();
    }
    if (!inInput && (event.metaKey || event.ctrlKey) && event.shiftKey && event.key.toLowerCase() === "s") {
      event.preventDefault();
      runPowerSync();
    }
  });

  el.searchBtn.addEventListener("click", async () => {
    await runSearch();
  });

  el.clearSearchBtn.addEventListener("click", () => {
    clearSearchInputs();
    state.searchMode = false;
    state.lastQuery = "";
    state.baseEvents = state.snapshot ? state.snapshot.timeline : [];
    state.similarEvents = [];
    el.searchMeta.textContent = "Showing today's timeline.";
    applyAndRender();
  });

  el.syncBtn.addEventListener("click", async () => {
    setNav("home");
    el.searchMeta.textContent = "Showing today's timeline.";
    await runSync({
      silent: false,
      lookbackHours: 24,
      includeAllHistory: false,
      browsers: ["chrome", "brave", "safari"],
      label: "Syncing...",
    });
  });

  if (el.powerBtn) {
    el.powerBtn.addEventListener("click", async () => {
      await runPowerSync();
    });
  }

  el.safariFullBtn.addEventListener("click", async () => {
    setNav("home");
    el.searchMeta.textContent = "Showing today's timeline.";
    await runSync({
      silent: false,
      lookbackHours: 24,
      includeAllHistory: true,
      browsers: ["safari"],
      label: "Importing full Safari history...",
    });
  });

  el.liveBtn.addEventListener("click", () => {
    setLiveSync(!state.liveSyncEnabled);
    showToast(`Live sync ${state.liveSyncEnabled ? "enabled" : "disabled"}.`);
  });

  el.reportBtn.addEventListener("click", async (event) => {
    await generateReport(event.shiftKey);
  });

  if (el.reportRefreshBtn) {
    el.reportRefreshBtn.addEventListener("click", async () => {
      await generateReport(true);
    });
  }

  if (el.downloadReportBtn) {
    el.downloadReportBtn.addEventListener("click", async () => {
      await downloadReportPdf(false);
    });
  }

  el.permissionBtn.addEventListener("click", async () => {
    await checkPermissions(false);
  });

  el.clearHistoryBtn.addEventListener("click", async () => {
    await clearWaveData();
  });

  if (el.captureWindowBtn) {
    el.captureWindowBtn.addEventListener("click", async () => {
      await captureSelectedWindow();
    });
  }

  if (el.deleteWindowBtn) {
    el.deleteWindowBtn.addEventListener("click", async () => {
      await deleteSelectedWindowData();
    });
  }

  if (el.clearWindowCaptureBtn) {
    el.clearWindowCaptureBtn.addEventListener("click", () => {
      state.windowCaptureEvents = [];
      renderWindowCapture();
      showToast("Captured window cleared.");
    });
  }

  el.startHour.addEventListener("change", updateCaptureHint);
  el.endHour.addEventListener("change", updateCaptureHint);

  el.viewButtons.forEach((button) => {
    button.addEventListener("click", () => {
      setViewMode(button.dataset.view || "list");
    });
  });

  el.browserFilterButtons.forEach((button) => {
    button.addEventListener("click", () => {
      setBrowserFilter(button.dataset.browser || "all");
    });
  });

  el.collectionFilterButtons.forEach((button) => {
    button.addEventListener("click", () => {
      setCollectionFilter(button.dataset.collection || "all");
    });
  });

  el.pillButtons.forEach((button) => {
    button.addEventListener("click", () => {
      setCollectionFilter(button.dataset.collection || "all");
    });
  });

  el.navButtons.forEach((button) => {
    button.addEventListener("click", () => {
      setNav(button.dataset.nav || "home");
    });
  });
}

(async function boot() {
  try {
    setupHourSelectors();
    renderWindowCapture();
    attachListeners();
    await loadSnapshot();
    await checkPermissions(true);
    await loadCachedReport();
    updateSavedCounts();
    updateHealthStrip();
    el.searchMeta.textContent = "Showing today's timeline.";
    el.lastAction.textContent = "Ready";
  } catch (error) {
    el.lastAction.textContent = "Backend unavailable";
    showToast(error.message || "Could not load data.");
  }
})();
