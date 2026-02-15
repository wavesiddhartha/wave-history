const el = {
  syncBtn: document.getElementById("syncBtn"),
  settingsBtn: document.getElementById("settingsBtn"),
  historyBtn: document.getElementById("historyBtn"),
  searchBtn: document.getElementById("searchBtn"),
  reportRefreshBtn: document.getElementById("reportRefreshBtn"),
  previewReportBtn: document.getElementById("previewReportBtn"),
  downloadReportBtn: document.getElementById("downloadReportBtn"),
  closeSettingsBtn: document.getElementById("closeSettingsBtn"),
  settingsModal: document.getElementById("settingsModal"),
  historyModal: document.getElementById("historyModal"),
  searchModal: document.getElementById("searchModal"),
  reportPreviewModal: document.getElementById("reportPreviewModal"),
  closeHistoryBtn: document.getElementById("closeHistoryBtn"),
  closeSearchBtn: document.getElementById("closeSearchBtn"),
  searchForm: document.getElementById("searchForm"),
  searchInput: document.getElementById("searchInput"),
  searchRunBtn: document.getElementById("searchRunBtn"),
  searchMeta: document.getElementById("searchMeta"),
  searchInsight: document.getElementById("searchInsight"),
  searchResultsPanel: document.getElementById("searchResultsPanel"),
  searchSimilarPanel: document.getElementById("searchSimilarPanel"),
  closePreviewBtn: document.getElementById("closePreviewBtn"),
  previewDownloadBtn: document.getElementById("previewDownloadBtn"),
  previewReadableBtn: document.getElementById("previewReadableBtn"),
  previewPdfBtn: document.getElementById("previewPdfBtn"),
  previewPdfPanel: document.getElementById("previewPdfPanel"),
  previewMeta: document.getElementById("previewMeta"),
  previewReadable: document.getElementById("previewReadable"),
  reportPreviewFrame: document.getElementById("reportPreviewFrame"),
  historySearchInput: document.getElementById("historySearchInput"),
  historyMeta: document.getElementById("historyMeta"),
  historyPanel: document.getElementById("historyPanel"),
  historyTabCount: document.getElementById("historyTabCount"),
  collectionsTabCount: document.getElementById("collectionsTabCount"),
  savedTabCount: document.getElementById("savedTabCount"),
  permissionBtn: document.getElementById("permissionBtn"),
  captureWindowBtn: document.getElementById("captureWindowBtn"),
  deleteWindowBtn: document.getElementById("deleteWindowBtn"),
  clearHistoryBtn: document.getElementById("clearHistoryBtn"),
  permissionText: document.getElementById("permissionText"),
  captureHint: document.getElementById("captureHint"),
  startHour: document.getElementById("startHour"),
  endHour: document.getElementById("endHour"),
  heroEvents: document.getElementById("heroEvents"),
  heroSubtitle: document.getElementById("heroSubtitle"),
  totalEvents: document.getElementById("totalEvents"),
  syncedBrowsers: document.getElementById("syncedBrowsers"),
  capturedEvents: document.getElementById("capturedEvents"),
  captureRange: document.getElementById("captureRange"),
  savedLinks: document.getElementById("savedLinks"),
  lastAction: document.getElementById("lastAction"),
  statusSyncAt: document.getElementById("statusSyncAt"),
  statusDay: document.getElementById("statusDay"),
  latestEventAt: document.getElementById("latestEventAt"),
  freshnessStatus: document.getElementById("freshnessStatus"),
  lastSyncAt: document.getElementById("lastSyncAt"),
  lastSyncInserted: document.getElementById("lastSyncInserted"),
  activeDay: document.getElementById("activeDay"),
  reportBody: document.getElementById("reportBody"),
  reportMetaEvents: document.getElementById("reportMetaEvents"),
  reportMetaDate: document.getElementById("reportMetaDate"),
  reportMetaModel: document.getElementById("reportMetaModel"),
  historyTabs: Array.from(document.querySelectorAll(".history-tab")),
  toast: document.getElementById("toast"),
};

const apiToken = typeof window !== "undefined" ? window.__WAVE_API_TOKEN__ || "" : "";
const SAVED_KEY = "wave_saved_events_v1";
const HISTORY_RENDER_LIMIT = 240;
const COLLECTION_RULES = [
  { key: "videos", label: "Videos", hints: ["youtube.com", "youtu.be", "netflix", "twitch", "vimeo", "primevideo"] },
  { key: "articles", label: "Articles", hints: ["medium.com", "wikipedia.org", "substack", "blog", "article", "docs"] },
  { key: "shopping", label: "Shopping", hints: ["amazon.", "ebay.", "walmart.", "flipkart.", "etsy.", "shop", "cart"] },
  { key: "social", label: "Social", hints: ["instagram.com", "facebook.com", "reddit.com", "x.com", "twitter.com", "linkedin.com"] },
  { key: "work", label: "Work / Learning", hints: ["github.com", "localhost", "vercel.com", "notion", "developer", "stack"] },
];

const state = {
  snapshot: null,
  byBrowser: {},
  lastSyncInserted: 0,
  lastSyncAt: null,
  currentReportDate: null,
  syncInFlight: false,
  saved: loadSavedStore(),
  historyTab: "history",
  historyQuery: "",
  searchQuery: "",
  searchPayload: null,
  searchInFlight: false,
  previewBlobUrl: null,
  previewMode: "readable",
};

function showToast(message, timeout = 2200) {
  if (!el.toast) {
    return;
  }
  el.toast.textContent = message;
  el.toast.classList.add("show");
  window.setTimeout(() => {
    el.toast.classList.remove("show");
  }, timeout);
}

async function copyToClipboard(text) {
  const value = String(text || "");
  if (!value) {
    throw new Error("Nothing to copy.");
  }

  if (navigator.clipboard && window.isSecureContext) {
    await navigator.clipboard.writeText(value);
    return;
  }

  const input = document.createElement("textarea");
  input.value = value;
  input.setAttribute("readonly", "");
  input.style.position = "fixed";
  input.style.opacity = "0";
  input.style.pointerEvents = "none";
  document.body.appendChild(input);
  input.select();
  const ok = document.execCommand("copy");
  input.remove();
  if (!ok) {
    throw new Error("Copy failed.");
  }
}

function openSettings() {
  if (!el.settingsModal) {
    return;
  }
  closePreview();
  closeHistory();
  closeSearch();
  el.settingsModal.hidden = false;
}

function closeSettings() {
  if (!el.settingsModal) {
    return;
  }
  el.settingsModal.hidden = true;
}

function openHistory() {
  if (!el.historyModal) {
    return;
  }
  closePreview();
  closeSettings();
  closeSearch();
  el.historyModal.hidden = false;
  renderHistoryPanel();
  if (el.historySearchInput) {
    el.historySearchInput.focus();
  }
}

function closeHistory() {
  if (!el.historyModal) {
    return;
  }
  el.historyModal.hidden = true;
}

function openSearch() {
  if (!el.searchModal) {
    return;
  }
  closePreview();
  closeHistory();
  closeSettings();
  renderSearchPanels();
  el.searchModal.hidden = false;
  if (el.searchInput) {
    el.searchInput.value = state.searchQuery;
    el.searchInput.focus();
    el.searchInput.select();
  }
}

function closeSearch() {
  if (!el.searchModal) {
    return;
  }
  el.searchModal.hidden = true;
}

function openPreview() {
  if (!el.reportPreviewModal) {
    return;
  }
  closeSearch();
  closeSettings();
  closeHistory();
  setPreviewMode("readable");
  el.reportPreviewModal.hidden = false;
}

function closePreview() {
  if (!el.reportPreviewModal) {
    return;
  }
  el.reportPreviewModal.hidden = true;
  if (el.reportPreviewFrame) {
    el.reportPreviewFrame.src = "about:blank";
  }
  if (state.previewBlobUrl) {
    window.URL.revokeObjectURL(state.previewBlobUrl);
    state.previewBlobUrl = null;
  }
}

function setPreviewMode(mode) {
  const resolved = mode === "pdf" ? "pdf" : "readable";
  state.previewMode = resolved;

  if (el.previewReadable) {
    el.previewReadable.hidden = resolved !== "readable";
  }
  if (el.previewPdfPanel) {
    el.previewPdfPanel.hidden = resolved !== "pdf";
  }
  if (el.previewReadableBtn) {
    el.previewReadableBtn.classList.toggle("active", resolved === "readable");
  }
  if (el.previewPdfBtn) {
    el.previewPdfBtn.classList.toggle("active", resolved === "pdf");
  }
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

function toTimeStamp(dateString) {
  if (!dateString) {
    return "-";
  }
  const dt = new Date(dateString);
  if (Number.isNaN(dt.getTime())) {
    return "-";
  }
  return dt.toLocaleString([], {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: true,
  });
}

function toClockLabel(dateString) {
  if (!dateString) {
    return "-";
  }
  const dt = new Date(dateString);
  if (Number.isNaN(dt.getTime())) {
    return "-";
  }
  return dt.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    hour12: true,
  });
}

function toDateLabel(dateString) {
  if (!dateString) {
    return "-";
  }
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

function toHourMinute(dateString) {
  if (!dateString) {
    return "-";
  }
  const dt = new Date(dateString);
  if (Number.isNaN(dt.getTime())) {
    return "-";
  }
  return dt.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    hour12: true,
  });
}

function formatHour(hour) {
  const suffix = hour < 12 ? "AM" : "PM";
  const display = hour % 12 === 0 ? 12 : hour % 12;
  return `${display}:00 ${suffix}`;
}

function setupHourSelectors() {
  if (!el.startHour || !el.endHour) {
    return;
  }

  const startFrag = document.createDocumentFragment();
  const endFrag = document.createDocumentFragment();
  for (let hour = 0; hour < 24; hour += 1) {
    const label = formatHour(hour);

    const startOption = document.createElement("option");
    startOption.value = String(hour);
    startOption.textContent = label;
    startFrag.appendChild(startOption);

    const endOption = document.createElement("option");
    endOption.value = String(hour);
    endOption.textContent = label;
    endFrag.appendChild(endOption);
  }

  el.startHour.appendChild(startFrag);
  el.endHour.appendChild(endFrag);
  el.startHour.value = "0";
  el.endHour.value = "0";
  updateCaptureHint();
}

function updateCaptureHint() {
  if (!el.captureHint || !el.startHour || !el.endHour) {
    return;
  }

  const start = Number(el.startHour.value);
  const end = Number(el.endHour.value);
  if (start === end) {
    el.captureHint.textContent = "All day (12:00 AM to 12:00 AM)";
    return;
  }

  el.captureHint.textContent = `${formatHour(start)} to ${formatHour(end)} (local)`;
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
  try {
    window.localStorage.setItem(SAVED_KEY, JSON.stringify(state.saved));
  } catch {
    // Ignore storage quota/runtime errors.
  }
}

function eventKey(event) {
  return `${event.browser || "unknown"}|${event.url || ""}|${event.visited_at || ""}`;
}

function isSaved(event) {
  return Boolean(state.saved[eventKey(event)]);
}

function saveEvent(event) {
  state.saved[eventKey(event)] = {
    browser: event.browser || "unknown",
    url: event.url || "",
    title: event.title || "Untitled",
    domain: event.domain || "",
    visited_at: event.visited_at || new Date().toISOString(),
  };
  persistSavedStore();
}

function unsaveEvent(event) {
  delete state.saved[eventKey(event)];
  persistSavedStore();
}

function savedCount() {
  return Object.keys(state.saved).length;
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

function eventCollection(event) {
  const hay = `${event.domain || ""} ${event.title || ""} ${event.url || ""}`.toLowerCase();
  for (const rule of COLLECTION_RULES) {
    if (rule.hints.some((hint) => hay.includes(hint))) {
      return rule;
    }
  }
  return { key: "general", label: "General Web" };
}

function updateSavedCounts() {
  const count = savedCount();
  if (el.savedLinks) {
    el.savedLinks.textContent = String(count);
  }
  if (el.savedTabCount) {
    el.savedTabCount.textContent = String(count);
  }
}

function computeCaptureRange(timeline) {
  if (!Array.isArray(timeline) || timeline.length === 0) {
    return "-";
  }

  const sorted = timeline
    .map((event) => new Date(event.visited_at))
    .filter((dt) => !Number.isNaN(dt.getTime()))
    .sort((a, b) => a.getTime() - b.getTime());

  if (!sorted.length) {
    return "-";
  }

  const start = sorted[0].toISOString();
  const end = sorted[sorted.length - 1].toISOString();
  return `${toHourMinute(start)}-${toHourMinute(end)}`;
}

function updateHealth(snapshot) {
  const timeline = Array.isArray(snapshot?.timeline) ? snapshot.timeline : [];
  const latest = timeline.length ? timeline[0]?.visited_at : null;

  if (el.activeDay) {
    el.activeDay.textContent = snapshot?.date ? toDateLabel(snapshot.date) : "-";
  }
  if (el.statusDay) {
    el.statusDay.textContent = snapshot?.date ? toDateLabel(snapshot.date) : "-";
  }
  if (el.lastSyncInserted) {
    el.lastSyncInserted.textContent = String(state.lastSyncInserted);
  }

  const syncLabel = state.lastSyncAt ? toClockLabel(state.lastSyncAt) : "-";
  if (el.lastSyncAt) {
    el.lastSyncAt.textContent = syncLabel;
  }
  if (el.statusSyncAt) {
    el.statusSyncAt.textContent = syncLabel;
  }

  if (!latest) {
    if (el.latestEventAt) {
      el.latestEventAt.textContent = "Latest: -";
    }
    if (el.freshnessStatus) {
      el.freshnessStatus.textContent = "-";
      el.freshnessStatus.className = "health-value dash";
    }
    return;
  }

  const latestDate = new Date(latest);
  if (Number.isNaN(latestDate.getTime())) {
    if (el.latestEventAt) {
      el.latestEventAt.textContent = "Latest: -";
    }
    if (el.freshnessStatus) {
      el.freshnessStatus.textContent = "-";
      el.freshnessStatus.className = "health-value dash";
    }
    return;
  }

  if (el.latestEventAt) {
    el.latestEventAt.textContent = `Latest: ${toTimeStamp(latest)}`;
  }

  const diffMinutes = Math.max(0, Math.round((Date.now() - latestDate.getTime()) / 60000));

  if (!el.freshnessStatus) {
    return;
  }

  if (diffMinutes <= 5) {
    el.freshnessStatus.textContent = `Fresh (${diffMinutes}m)`;
    el.freshnessStatus.className = "health-value fresh";
    return;
  }

  if (diffMinutes <= 30) {
    el.freshnessStatus.textContent = `Warm (${diffMinutes}m)`;
    el.freshnessStatus.className = "health-value fresh";
    return;
  }

  el.freshnessStatus.textContent = `Stale (${diffMinutes}m)`;
  el.freshnessStatus.className = "health-value stale";
}

function renderSnapshot(snapshot) {
  const total = Number(snapshot?.total_events || 0);
  const timeline = Array.isArray(snapshot?.timeline) ? snapshot.timeline : [];
  const roots = new Set(timeline.map((event) => browserRoot(event.browser)).filter(Boolean));

  if (el.heroEvents) {
    el.heroEvents.textContent = String(total);
  }
  if (el.heroSubtitle) {
    el.heroSubtitle.textContent = `Events captured on ${toDateLabel(snapshot?.date)}`;
  }

  if (el.totalEvents) {
    el.totalEvents.textContent = String(total);
  }
  if (el.syncedBrowsers) {
    el.syncedBrowsers.textContent = String(roots.size);
  }
  if (el.capturedEvents) {
    el.capturedEvents.textContent = String(timeline.length);
  }
  if (el.captureRange) {
    el.captureRange.textContent = computeCaptureRange(timeline);
  }
  if (el.savedLinks) {
    el.savedLinks.textContent = String(savedCount());
  }

  updateHealth(snapshot);
  renderHistoryPanel();
}

function historyMatchesQuery(event, query) {
  if (!query) {
    return true;
  }
  const hay = `${event.title || ""} ${event.domain || ""} ${event.url || ""} ${event.browser || ""}`.toLowerCase();
  return hay.includes(query);
}

function getHistoryEvents() {
  const timeline = Array.isArray(state.snapshot?.timeline) ? state.snapshot.timeline : [];
  return timeline.slice();
}

function getSavedEvents() {
  const entries = Object.values(state.saved || {});
  entries.sort((a, b) => {
    const left = new Date(a.visited_at || 0).getTime();
    const right = new Date(b.visited_at || 0).getTime();
    return right - left;
  });
  return entries;
}

function setHistoryTab(tab) {
  state.historyTab = tab;
  el.historyTabs.forEach((button) => {
    button.classList.toggle("active", button.dataset.historyTab === tab);
  });
  renderHistoryPanel();
}

function createHistoryItem(event, options = {}) {
  const onItemChange = typeof options.onItemChange === "function" ? options.onItemChange : renderHistoryPanel;
  const item = document.createElement("article");
  item.className = "history-item";

  const top = document.createElement("div");
  top.className = "history-item-top";

  const browser = document.createElement("span");
  browser.className = "history-browser";
  browser.textContent = browserLabel(event.browser);

  const time = document.createElement("span");
  time.className = "history-time";
  time.textContent = toTimeStamp(event.visited_at);

  top.append(browser, time);

  const title = document.createElement("h4");
  title.className = "history-title";
  title.textContent = event.title || "Untitled";

  const link = document.createElement("a");
  link.className = "history-url";
  link.href = event.url;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  link.textContent = event.url;

  const actions = document.createElement("div");
  actions.className = "history-actions";

  const openBtn = document.createElement("button");
  openBtn.className = "history-action-btn";
  openBtn.type = "button";
  openBtn.textContent = "Open";
  openBtn.addEventListener("click", () => {
    if (!event.url) {
      showToast("No URL available for this entry.");
      return;
    }
    window.open(event.url, "_blank", "noopener,noreferrer");
  });

  const copyBtn = document.createElement("button");
  copyBtn.className = "history-action-btn";
  copyBtn.type = "button";
  copyBtn.textContent = "Copy";
  copyBtn.addEventListener("click", async () => {
    try {
      await copyToClipboard(event.url || "");
      showToast("Link copied.");
    } catch {
      showToast("Could not copy link.");
    }
  });

  const saveBtn = document.createElement("button");
  saveBtn.type = "button";
  const refreshSaveButton = () => {
    const saved = isSaved(event);
    saveBtn.className = `history-action-btn ${saved ? "saved" : ""}`;
    saveBtn.textContent = saved ? "Unsave" : "Save";
  };
  refreshSaveButton();
  saveBtn.addEventListener("click", () => {
    if (isSaved(event)) {
      unsaveEvent(event);
      showToast("Removed from saved.");
    } else {
      saveEvent(event);
      showToast("Saved.");
    }
    updateSavedCounts();
    onItemChange();
    refreshSaveButton();
  });

  actions.append(openBtn, copyBtn, saveBtn);
  item.append(top, title, link, actions);
  return item;
}

function createEmptyNode(message) {
  const empty = document.createElement("p");
  empty.className = "history-empty";
  empty.textContent = message;
  return empty;
}

function renderHistoryList(events, options = {}) {
  const list = document.createElement("div");
  list.className = "history-list";
  events.forEach((event) => {
    list.appendChild(createHistoryItem(event, options));
  });
  return list;
}

function renderCollections(events) {
  const byCollection = new Map();
  events.forEach((event) => {
    const collection = eventCollection(event);
    const key = collection.key;
    if (!byCollection.has(key)) {
      byCollection.set(key, { label: collection.label, events: [] });
    }
    byCollection.get(key).events.push(event);
  });

  const container = document.createElement("div");
  if (!byCollection.size) {
    container.appendChild(createEmptyNode("No collection matches for the selected filter."));
    return container;
  }

  Array.from(byCollection.values())
    .sort((a, b) => b.events.length - a.events.length)
    .forEach((group) => {
      const block = document.createElement("section");
      block.className = "collection-group";

      const heading = document.createElement("h4");
      heading.className = "collection-title";
      heading.textContent = `${group.label} (${group.events.length})`;

      block.appendChild(heading);
      block.appendChild(renderHistoryList(group.events));
      container.appendChild(block);
    });

  return container;
}

function renderHistoryPanel() {
  if (!el.historyPanel) {
    return;
  }

  const query = state.historyQuery.trim().toLowerCase();
  const allEvents = getHistoryEvents();
  const filteredAll = allEvents.filter((event) => historyMatchesQuery(event, query));
  const savedEvents = getSavedEvents().filter((event) => historyMatchesQuery(event, query));
  const limitedHistory = filteredAll.slice(0, HISTORY_RENDER_LIMIT);
  const limitedSaved = savedEvents.slice(0, HISTORY_RENDER_LIMIT);

  const collectionMap = new Map();
  filteredAll.forEach((event) => {
    const collection = eventCollection(event);
    collectionMap.set(collection.key, true);
  });

  if (el.historyTabCount) {
    el.historyTabCount.textContent = String(allEvents.length);
  }
  if (el.collectionsTabCount) {
    el.collectionsTabCount.textContent = String(collectionMap.size);
  }
  updateSavedCounts();

  el.historyPanel.innerHTML = "";

  if (state.historyTab === "history") {
    const trimmed = filteredAll.length > HISTORY_RENDER_LIMIT;
    if (el.historyMeta) {
      el.historyMeta.textContent = trimmed
        ? `Showing ${limitedHistory.length} of ${filteredAll.length} history items. Refine search for full precision.`
        : `Showing ${filteredAll.length} history item${filteredAll.length === 1 ? "" : "s"}.`;
    }
    if (!filteredAll.length) {
      el.historyPanel.appendChild(createEmptyNode("No history items found."));
      return;
    }
    el.historyPanel.appendChild(renderHistoryList(limitedHistory));
    return;
  }

  if (state.historyTab === "collections") {
    if (el.historyMeta) {
      el.historyMeta.textContent = `Showing ${collectionMap.size} collection${collectionMap.size === 1 ? "" : "s"}.`;
    }
    el.historyPanel.appendChild(renderCollections(limitedHistory));
    return;
  }

  const trimmed = savedEvents.length > HISTORY_RENDER_LIMIT;
  if (el.historyMeta) {
    el.historyMeta.textContent = trimmed
      ? `Showing ${limitedSaved.length} of ${savedEvents.length} saved items. Refine search for full precision.`
      : `Showing ${savedEvents.length} saved item${savedEvents.length === 1 ? "" : "s"}.`;
  }
  if (!savedEvents.length) {
    el.historyPanel.appendChild(createEmptyNode("No saved links yet."));
    return;
  }
  el.historyPanel.appendChild(renderHistoryList(limitedSaved));
}

function renderSearchEmptyState() {
  if (el.searchMeta) {
    el.searchMeta.textContent = "Analysis uses only Wave-captured history.";
  }
  if (el.searchInsight) {
    el.searchInsight.innerHTML = "";
    el.searchInsight.appendChild(paragraph("Run a search to see analyzed insights from your browsing history data."));
  }
  if (el.searchResultsPanel) {
    el.searchResultsPanel.innerHTML = "";
    el.searchResultsPanel.appendChild(createEmptyNode("No search results yet."));
  }
  if (el.searchSimilarPanel) {
    el.searchSimilarPanel.innerHTML = "";
    el.searchSimilarPanel.appendChild(createEmptyNode("Similar links will appear after search."));
  }
}

function describeSearchAnalysis(payload) {
  const results = Array.isArray(payload?.results) ? payload.results : [];
  const similar = Array.isArray(payload?.similar) ? payload.similar : [];
  const totalMatches = Number(payload?.total_matches || results.length);
  const query = String(payload?.query || "").trim();
  const combined = [...results, ...similar];

  if (!query) {
    return {
      summary: "Enter a keyword to analyze your captured browsing history.",
      bullets: [],
    };
  }

  if (!totalMatches) {
    return {
      summary: `No history match was found for "${query}" in Wave data yet.`,
      bullets: [
        "Try another keyword or sync recent browser activity first.",
        "Analysis is generated only from your captured Wave history data.",
      ],
    };
  }

  const domainCount = new Map();
  const browserCount = new Map();
  let titleHits = 0;
  let urlHits = 0;
  const queryLower = query.toLowerCase();

  results.forEach((event) => {
    const domain = String(event.domain || "unknown");
    domainCount.set(domain, (domainCount.get(domain) || 0) + 1);

    const browser = browserRoot(event.browser) || "unknown";
    browserCount.set(browser, (browserCount.get(browser) || 0) + 1);

    const title = String(event.title || "").toLowerCase();
    const url = String(event.url || "").toLowerCase();
    if (title.includes(queryLower)) {
      titleHits += 1;
    }
    if (url.includes(queryLower) || domain.toLowerCase().includes(queryLower)) {
      urlHits += 1;
    }
  });

  const topDomains = Array.from(domainCount.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, 4)
    .map(([domain, count]) => `${domain} (${count})`);

  const browserMix = Array.from(browserCount.entries())
    .sort((a, b) => b[1] - a[1])
    .map(([browser, count]) => `${browser} (${count})`);

  const revisitDomains = Array.from(domainCount.values()).filter((count) => count >= 2).length;

  const times = combined
    .map((event) => new Date(event.visited_at))
    .filter((dt) => !Number.isNaN(dt.getTime()))
    .sort((a, b) => a.getTime() - b.getTime());

  const rangeLine =
    times.length > 1
      ? `Activity window: ${toTimeStamp(times[0].toISOString())} to ${toTimeStamp(times[times.length - 1].toISOString())}.`
      : times.length === 1
        ? `Matched activity time: ${toTimeStamp(times[0].toISOString())}.`
        : "Activity window: unavailable.";

  const summary = `"${query}" matched ${totalMatches} history event${totalMatches === 1 ? "" : "s"} in Wave.`;
  const bullets = [
    `Direct results shown: ${results.length}. Similar links from same domains: ${similar.length}.`,
    `Top domains for this term: ${topDomains.length ? topDomains.join(", ") : "none"}.`,
    `Browser mix: ${browserMix.length ? browserMix.join(", ") : "none"}.`,
    `Keyword hit quality: ${titleHits} title hit${titleHits === 1 ? "" : "s"}, ${urlHits} URL/domain hit${urlHits === 1 ? "" : "s"}.`,
    `Repeat-interest signal: ${revisitDomains} domain${revisitDomains === 1 ? "" : "s"} revisited multiple times.`,
    rangeLine,
    "This analysis is generated only from Wave-captured history data.",
  ];

  return { summary, bullets };
}

function renderSearchPanels() {
  const payload = state.searchPayload;
  if (!payload) {
    renderSearchEmptyState();
    return;
  }

  const results = Array.isArray(payload.results) ? payload.results : [];
  const similar = Array.isArray(payload.similar) ? payload.similar : [];
  const totalMatches = Number(payload.total_matches || results.length);
  const query = String(payload.query || state.searchQuery || "").trim();

  if (el.searchMeta) {
    el.searchMeta.textContent = `${totalMatches} total match${totalMatches === 1 ? "" : "es"} for "${query}". Showing ${
      results.length
    } direct result${results.length === 1 ? "" : "s"} and ${similar.length} similar link${similar.length === 1 ? "" : "s"}.`;
  }

  if (el.searchResultsPanel) {
    el.searchResultsPanel.innerHTML = "";
    if (!results.length) {
      el.searchResultsPanel.appendChild(createEmptyNode("No direct history matches for this term."));
    } else {
      el.searchResultsPanel.appendChild(renderHistoryList(results, { onItemChange: renderSearchPanels }));
    }
  }

  if (el.searchSimilarPanel) {
    el.searchSimilarPanel.innerHTML = "";
    if (!similar.length) {
      el.searchSimilarPanel.appendChild(createEmptyNode("No similar links found from matching domains."));
    } else {
      el.searchSimilarPanel.appendChild(renderHistoryList(similar, { onItemChange: renderSearchPanels }));
    }
  }

  if (el.searchInsight) {
    const analysis = describeSearchAnalysis(payload);
    el.searchInsight.innerHTML = "";
    el.searchInsight.appendChild(paragraph(analysis.summary));
    if (analysis.bullets.length) {
      const list = document.createElement("ul");
      analysis.bullets.forEach((bullet) => {
        const li = document.createElement("li");
        li.textContent = bullet;
        list.appendChild(li);
      });
      el.searchInsight.appendChild(list);
    }
  }
}

async function runHistorySearch(rawQuery) {
  const query = String(rawQuery || "").trim();
  if (!query) {
    showToast("Enter a search term first.");
    return;
  }
  if (state.searchInFlight) {
    return;
  }

  state.searchInFlight = true;
  if (el.searchRunBtn) {
    el.searchRunBtn.disabled = true;
  }
  if (el.lastAction) {
    el.lastAction.textContent = `Searching "${query}"...`;
  }

  try {
    const params = new URLSearchParams({
      q: query,
      limit: "80",
    });
    const payload = await api(`/api/search?${params.toString()}`);

    state.searchQuery = query;
    state.searchPayload = payload;
    renderSearchPanels();

    if (el.lastAction) {
      el.lastAction.textContent = `Search ready (${payload.total_matches} matches)`;
    }
    showToast(`Search complete: ${payload.total_matches} matches.`);
  } catch (error) {
    if (el.lastAction) {
      el.lastAction.textContent = "Search failed";
    }
    showToast(error.message || "Could not search history.");
  } finally {
    state.searchInFlight = false;
    if (el.searchRunBtn) {
      el.searchRunBtn.disabled = false;
    }
  }
}

function paragraph(text) {
  const p = document.createElement("p");
  p.textContent = text;
  return p;
}

function makeBulletSentence(label, values, fallback = "No clear signals.", maxItems = 5) {
  if (!Array.isArray(values) || !values.length) {
    return `${label}: ${fallback}`;
  }
  return `${label}: ${values.slice(0, maxItems).join(", ")}.`;
}

function renderReport(report) {
  const details = report?.details && typeof report.details === "object" ? report.details : {};
  const narrative = String(details.narrative || "").trim();
  const summary = String(report?.summary || "No summary available.").trim();
  const examinationSummary = String(details.examination_summary || "").trim();
  const examinationGrade = String(details.examination_grade || "").trim();
  const parsedScore = Number(details.overall_score);
  const overallScore = Number.isFinite(parsedScore) ? Math.max(0, Math.min(100, Math.round(parsedScore))) : null;
  const scorecard = Array.isArray(details.scorecard) ? details.scorecard : [];
  const detailedFindings = Array.isArray(details.detailed_findings) ? details.detailed_findings : [];
  const topDomains = Array.isArray(state.snapshot?.top_domains) ? state.snapshot.top_domains : [];

  const topDomainLine = topDomains.length
    ? `Top domains today: ${topDomains.slice(0, 6).map((item) => `${item.domain} (${item.count})`).join(", ")}.`
    : "Top domains today: No significant domain concentration yet.";
  const examLine =
    examinationGrade || overallScore !== null
      ? `Examination Result: Grade ${examinationGrade || "-"} | Overall Score ${overallScore ?? "-"}/100.`
      : "";

  const paragraphs = [
    examLine,
    examinationSummary || summary,
    narrative && narrative !== examinationSummary ? narrative : "",
    makeBulletSentence("Scorecard", scorecard, "No scorecard generated.", 6),
    makeBulletSentence("Detailed findings", detailedFindings, "No detailed findings generated.", 8),
    topDomainLine,
    makeBulletSentence("Behavior patterns", details.behavior_patterns),
    makeBulletSentence("Time insights", details.time_insights),
    makeBulletSentence("Category insights", details.category_insights),
    makeBulletSentence("Intent signals", details.intent_signals),
    makeBulletSentence("Focus gaps", details.focus_gaps),
    makeBulletSentence("Risk flags", report?.risk_flags, "No critical risks detected."),
    makeBulletSentence("Recommendations", details.recommendations),
  ].filter(Boolean);

  if (el.reportBody) {
    el.reportBody.innerHTML = "";
    const fragment = document.createDocumentFragment();
    paragraphs.forEach((line) => {
      fragment.appendChild(paragraph(line));
    });
    el.reportBody.appendChild(fragment);
  }

  if (el.reportMetaEvents) {
    el.reportMetaEvents.textContent = String(report?.source_events || 0);
  }
  if (el.reportMetaDate) {
    el.reportMetaDate.textContent = toDateLabel(report?.date);
  }
  if (el.reportMetaModel) {
    el.reportMetaModel.textContent = String(report?.model || "-");
  }

  state.currentReportDate = report?.date || null;
}

function renderPreviewReadable(report) {
  if (!el.previewReadable) {
    return;
  }

  const details = report?.details && typeof report.details === "object" ? report.details : {};
  const parsedScore = Number(details.overall_score);
  const overallScore = Number.isFinite(parsedScore) ? Math.max(0, Math.min(100, Math.round(parsedScore))) : null;
  const examinationGrade = String(details.examination_grade || "-").trim();
  const sourceEvents = Number(report?.source_events || state.snapshot?.total_events || 0);
  const summary = String(details.examination_summary || report?.summary || "No summary available.").trim();

  const statItems = [
    { label: "Grade", value: examinationGrade || "-" },
    { label: "Score", value: overallScore === null ? "-" : `${overallScore}/100` },
    { label: "Events", value: String(sourceEvents) },
    { label: "Date", value: toDateLabel(report?.date || state.snapshot?.date) },
  ];

  const listOrFallback = (value, fallback, maxItems = 6) => {
    if (!Array.isArray(value) || !value.length) {
      return [fallback];
    }
    return value.slice(0, maxItems).map((item) => String(item || "").trim()).filter(Boolean);
  };

  const sections = [
    { title: "Summary", type: "paragraph", content: summary, wide: true },
    {
      title: "Highlights",
      type: "list",
      content: listOrFallback(details.detailed_findings, "No highlights generated.", 6),
    },
    {
      title: "Behavior Patterns",
      type: "list",
      content: listOrFallback(details.behavior_patterns, "No behavior pattern insights generated.", 5),
    },
    {
      title: "Focus Gaps",
      type: "list",
      content: listOrFallback(details.focus_gaps, "No major focus gaps detected.", 5),
    },
    {
      title: "Risk Flags",
      type: "list",
      content: listOrFallback(report?.risk_flags, "No critical risk flags detected.", 5),
    },
    {
      title: "Recommendations",
      type: "list",
      content: listOrFallback(details.recommendations, "No recommendations generated.", 6),
      wide: true,
    },
  ];

  el.previewReadable.innerHTML = "";

  const top = document.createElement("section");
  top.className = "readable-top";
  statItems.forEach((item) => {
    const card = document.createElement("article");
    card.className = "readable-stat";

    const label = document.createElement("p");
    label.className = "readable-stat-label";
    label.textContent = item.label;

    const value = document.createElement("p");
    value.className = "readable-stat-value";
    value.textContent = item.value;

    card.append(label, value);
    top.appendChild(card);
  });

  const grid = document.createElement("section");
  grid.className = "readable-grid";
  sections.forEach((section) => {
    const block = document.createElement("article");
    block.className = `readable-section${section.wide ? " wide" : ""}`;

    const title = document.createElement("h4");
    title.textContent = section.title;
    block.appendChild(title);

    if (section.type === "paragraph") {
      const text = document.createElement("p");
      text.textContent = String(section.content || "No data available.");
      block.appendChild(text);
    } else {
      const list = document.createElement("ul");
      section.content.forEach((line) => {
        const li = document.createElement("li");
        li.textContent = line;
        list.appendChild(li);
      });
      block.appendChild(list);
    }

    grid.appendChild(block);
  });

  el.previewReadable.append(top, grid);
}

async function loadSnapshot() {
  const snapshot = await api("/api/today");
  state.snapshot = snapshot;
  renderSnapshot(snapshot);
}

async function checkPermissions(silent = false) {
  try {
    const status = await api("/api/permissions");
    const safari = status.browsers.find((item) => item.browser === "safari");
    if (safari && el.permissionText) {
      el.permissionText.textContent = `Safari: ${safari.status} | ${safari.message}`;
    }

    const ready = status.browsers.filter((item) => item.status === "ready").length;
    if (el.syncedBrowsers && !state.syncInFlight) {
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
  captureStartHour = null,
  captureEndHour = null,
  label = "Syncing...",
} = {}) {
  if (state.syncInFlight) {
    return false;
  }

  state.syncInFlight = true;
  if (el.syncBtn) {
    el.syncBtn.disabled = true;
  }
  if (el.captureWindowBtn) {
    el.captureWindowBtn.disabled = true;
  }
  if (el.deleteWindowBtn) {
    el.deleteWindowBtn.disabled = true;
  }
  if (el.lastAction) {
    el.lastAction.textContent = label;
  }

  try {
    const body = {
      lookback_hours: lookbackHours,
      include_all_history: includeAllHistory,
      browsers: ["chrome", "brave", "safari"],
    };

    const hasWindow =
      Number.isInteger(captureStartHour) &&
      Number.isInteger(captureEndHour) &&
      captureStartHour >= 0 &&
      captureStartHour <= 23 &&
      captureEndHour >= 0 &&
      captureEndHour <= 23;

    if (hasWindow) {
      body.capture_start_hour = captureStartHour;
      body.capture_end_hour = captureEndHour;
    }

    const result = await api("/api/sync", {
      method: "POST",
      body: JSON.stringify(body),
    });

    state.byBrowser = result.by_browser || {};
    state.lastSyncInserted = Number(result.inserted || 0);
    state.lastSyncAt = new Date().toISOString();

    await loadSnapshot();
    await checkPermissions(true);

    if (el.lastAction) {
      el.lastAction.textContent = `Synced ${state.lastSyncInserted} new events`;
    }

    if (!silent) {
      showToast(`Sync complete: ${state.lastSyncInserted} new event${state.lastSyncInserted === 1 ? "" : "s"}.`);
    }
    return true;
  } catch (error) {
    if (el.lastAction) {
      el.lastAction.textContent = "Sync failed";
    }
    showToast(error.message || "Sync failed.");
    return false;
  } finally {
    state.syncInFlight = false;
    if (el.syncBtn) {
      el.syncBtn.disabled = false;
    }
    if (el.captureWindowBtn) {
      el.captureWindowBtn.disabled = false;
    }
    if (el.deleteWindowBtn) {
      el.deleteWindowBtn.disabled = false;
    }
  }
}

async function captureSelectedWindow() {
  const start = Number(el.startHour?.value);
  const end = Number(el.endHour?.value);

  const synced = await runSync({
    silent: true,
    lookbackHours: 24,
    includeAllHistory: false,
    captureStartHour: start,
    captureEndHour: end,
    label: "Capturing selected window...",
  });

  if (!synced) {
    return;
  }

  if (el.lastAction) {
    el.lastAction.textContent = "Capture window synced";
  }
  showToast("Capture window imported.");
}

async function deleteSelectedWindowData() {
  const start = Number(el.startHour?.value);
  const end = Number(el.endHour?.value);
  const rangeLabel = `${formatHour(start)} to ${formatHour(end)}`;
  const day = state.snapshot?.date || "today";

  const ok = window.confirm(`Delete Wave history between ${rangeLabel} for ${day}?`);
  if (!ok) {
    return;
  }

  if (el.deleteWindowBtn) {
    el.deleteWindowBtn.disabled = true;
  }

  if (el.lastAction) {
    el.lastAction.textContent = "Deleting selected window...";
  }

  try {
    const payload = await api("/api/history/window/delete", {
      method: "POST",
      body: JSON.stringify({
        date: state.snapshot?.date || null,
        capture_start_hour: start,
        capture_end_hour: end,
      }),
    });

    await loadSnapshot();
    if (el.lastAction) {
      el.lastAction.textContent = "Selected window deleted";
    }
    showToast(`Deleted ${payload.deleted_events} event${payload.deleted_events === 1 ? "" : "s"}.`);
  } catch (error) {
    if (el.lastAction) {
      el.lastAction.textContent = "Window delete failed";
    }
    showToast(error.message || "Could not delete selected window.");
  } finally {
    if (el.deleteWindowBtn) {
      el.deleteWindowBtn.disabled = false;
    }
  }
}

async function clearWaveData() {
  const ok = window.confirm("Delete all Wave app history and cached reports? This cannot be undone.");
  if (!ok) {
    return;
  }

  if (el.clearHistoryBtn) {
    el.clearHistoryBtn.disabled = true;
  }
  if (el.lastAction) {
    el.lastAction.textContent = "Deleting Wave data...";
  }

  try {
    const payload = await api("/api/history/clear", {
      method: "POST",
      body: JSON.stringify({ include_reports: true }),
    });

    state.snapshot = null;
    state.lastSyncInserted = 0;
    state.lastSyncAt = null;
    state.saved = {};
    state.searchQuery = "";
    state.searchPayload = null;
    persistSavedStore();
    renderSnapshot({ date: null, total_events: 0, timeline: [] });
    resetReport();
    renderSearchPanels();
    if (el.searchInput) {
      el.searchInput.value = "";
    }
    closePreview();
    renderHistoryPanel();

    if (el.lastAction) {
      el.lastAction.textContent = "Wave data deleted";
    }

    showToast(`Deleted ${payload.deleted_events} events and ${payload.deleted_reports} reports.`);
  } catch (error) {
    if (el.lastAction) {
      el.lastAction.textContent = "Delete failed";
    }
    showToast(error.message || "Could not delete data.");
  } finally {
    if (el.clearHistoryBtn) {
      el.clearHistoryBtn.disabled = false;
    }
  }
}

function resetReport() {
  state.currentReportDate = null;
  if (el.reportBody) {
    el.reportBody.innerHTML =
      "<p>Wave captures your browser events and builds a detailed examination-result report from today's activity. Click <strong>Refresh Analysis</strong> to generate the latest deep analysis.</p>";
  }
  if (el.reportMetaEvents) {
    el.reportMetaEvents.textContent = "0";
  }
  if (el.reportMetaDate) {
    el.reportMetaDate.textContent = "-";
  }
  if (el.reportMetaModel) {
    el.reportMetaModel.textContent = "-";
  }
}

async function generateReport(forceRefresh = true) {
  if (el.reportRefreshBtn) {
    el.reportRefreshBtn.disabled = true;
  }
  if (el.lastAction) {
    el.lastAction.textContent = forceRefresh ? "Refreshing AI report..." : "Loading AI report...";
  }

  try {
    const synced = await runSync({
      silent: true,
      lookbackHours: 24,
      includeAllHistory: false,
      label: "Syncing before AI report...",
    });

    if (!synced) {
      throw new Error("Sync failed before report generation.");
    }

    const report = await api("/api/report", {
      method: "POST",
      body: JSON.stringify({ force_refresh: forceRefresh }),
    });
    renderReport(report);

    if (el.lastAction) {
      el.lastAction.textContent = "AI report ready";
    }
    showToast(forceRefresh ? "Report refreshed." : "Report ready.");
  } catch (error) {
    if (el.lastAction) {
      el.lastAction.textContent = "AI report failed";
    }
    showToast(error.message || "Could not generate report.");
  } finally {
    if (el.reportRefreshBtn) {
      el.reportRefreshBtn.disabled = false;
    }
  }
}

async function loadCachedReport() {
  try {
    const report = await api("/api/report");
    renderReport(report);
  } catch {
    resetReport();
  }
}

async function requestReportPdf(forceRefresh = false) {
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
  return { blob, filename };
}

async function openReportPreview() {
  if (el.previewReportBtn) {
    el.previewReportBtn.disabled = true;
  }
  if (el.previewDownloadBtn) {
    el.previewDownloadBtn.disabled = true;
  }
  if (el.lastAction) {
    el.lastAction.textContent = "Preparing report preview...";
  }

  try {
    openPreview();
    if (el.previewMeta) {
      el.previewMeta.textContent = "Preparing preview...";
    }

    const report = await api("/api/report", {
      method: "POST",
      body: JSON.stringify({ force_refresh: false }),
    });
    renderReport(report);
    renderPreviewReadable(report);

    if (el.previewMeta) {
      const modelLabel = String(report?.model || "-");
      el.previewMeta.textContent = `${toDateLabel(report?.date)} | ${report?.source_events || 0} events | ${modelLabel}`;
    }

    const { blob } = await requestReportPdf(false);
    if (state.previewBlobUrl) {
      window.URL.revokeObjectURL(state.previewBlobUrl);
      state.previewBlobUrl = null;
    }
    state.previewBlobUrl = window.URL.createObjectURL(blob);
    if (el.reportPreviewFrame) {
      el.reportPreviewFrame.src = `${state.previewBlobUrl}#zoom=page-width&view=FitH`;
    }

    if (el.lastAction) {
      el.lastAction.textContent = "Report preview ready";
    }
    setPreviewMode("readable");
    showToast("Preview ready.");
  } catch (error) {
    if (el.previewMeta) {
      el.previewMeta.textContent = "Preview unavailable";
    }
    if (el.previewReadable) {
      el.previewReadable.innerHTML = "";
      el.previewReadable.appendChild(
        paragraph(error.message || "Could not prepare report preview. Try refreshing analysis first."),
      );
    }
    if (el.lastAction) {
      el.lastAction.textContent = "Preview failed";
    }
    showToast(error.message || "Could not prepare report preview.");
  } finally {
    if (el.previewReportBtn) {
      el.previewReportBtn.disabled = false;
    }
    if (el.previewDownloadBtn) {
      el.previewDownloadBtn.disabled = false;
    }
  }
}

async function downloadReportPdf(forceRefresh = false) {
  if (el.downloadReportBtn) {
    el.downloadReportBtn.disabled = true;
  }
  if (el.previewDownloadBtn) {
    el.previewDownloadBtn.disabled = true;
  }
  if (el.lastAction) {
    el.lastAction.textContent = "Preparing PDF report...";
  }

  try {
    const { blob, filename } = await requestReportPdf(forceRefresh);

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

    if (el.lastAction) {
      el.lastAction.textContent = "Report PDF downloaded";
    }
    showToast(isSafari ? "PDF opened. Save/download from the opened tab." : "Detailed PDF report downloaded.");
  } catch (error) {
    if (el.lastAction) {
      el.lastAction.textContent = "PDF download failed";
    }
    showToast(error.message || "Could not download PDF report.");
  } finally {
    if (el.downloadReportBtn) {
      el.downloadReportBtn.disabled = false;
    }
    if (el.previewDownloadBtn) {
      el.previewDownloadBtn.disabled = false;
    }
  }
}

function attachListeners() {
  if (el.settingsBtn) {
    el.settingsBtn.addEventListener("click", openSettings);
  }
  if (el.historyBtn) {
    el.historyBtn.addEventListener("click", openHistory);
  }
  if (el.searchBtn) {
    el.searchBtn.addEventListener("click", openSearch);
  }
  if (el.closeSettingsBtn) {
    el.closeSettingsBtn.addEventListener("click", closeSettings);
  }
  if (el.closeHistoryBtn) {
    el.closeHistoryBtn.addEventListener("click", closeHistory);
  }
  if (el.closeSearchBtn) {
    el.closeSearchBtn.addEventListener("click", closeSearch);
  }

  document.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) {
      return;
    }
    if (target.dataset.closeModal === "true") {
      closeSettings();
    }
    if (target.dataset.closeHistory === "true") {
      closeHistory();
    }
    if (target.dataset.closeSearch === "true") {
      closeSearch();
    }
    if (target.dataset.closePreview === "true") {
      closePreview();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeSettings();
      closeHistory();
      closeSearch();
      closePreview();
    }
  });

  if (el.startHour) {
    el.startHour.addEventListener("change", updateCaptureHint);
  }
  if (el.endHour) {
    el.endHour.addEventListener("change", updateCaptureHint);
  }

  if (el.historySearchInput) {
    el.historySearchInput.addEventListener("input", () => {
      state.historyQuery = el.historySearchInput.value || "";
      renderHistoryPanel();
    });
  }

  if (el.searchForm) {
    el.searchForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      await runHistorySearch(el.searchInput?.value || "");
    });
  }

  el.historyTabs.forEach((button) => {
    button.addEventListener("click", () => {
      setHistoryTab(button.dataset.historyTab || "history");
    });
  });

  if (el.syncBtn) {
    el.syncBtn.addEventListener("click", async () => {
      await runSync({
        silent: false,
        lookbackHours: 24,
        includeAllHistory: false,
        label: "Syncing...",
      });
    });
  }

  if (el.permissionBtn) {
    el.permissionBtn.addEventListener("click", async () => {
      await checkPermissions(false);
    });
  }

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

  if (el.clearHistoryBtn) {
    el.clearHistoryBtn.addEventListener("click", async () => {
      await clearWaveData();
    });
  }

  if (el.reportRefreshBtn) {
    el.reportRefreshBtn.addEventListener("click", async () => {
      await generateReport(true);
    });
  }

  if (el.previewReportBtn) {
    el.previewReportBtn.addEventListener("click", async () => {
      await openReportPreview();
    });
  }

  if (el.downloadReportBtn) {
    el.downloadReportBtn.addEventListener("click", async () => {
      await downloadReportPdf(false);
    });
  }

  if (el.previewDownloadBtn) {
    el.previewDownloadBtn.addEventListener("click", async () => {
      await downloadReportPdf(false);
    });
  }

  if (el.previewReadableBtn) {
    el.previewReadableBtn.addEventListener("click", () => {
      setPreviewMode("readable");
    });
  }

  if (el.previewPdfBtn) {
    el.previewPdfBtn.addEventListener("click", () => {
      setPreviewMode("pdf");
    });
  }

  if (el.closePreviewBtn) {
    el.closePreviewBtn.addEventListener("click", closePreview);
  }
}

(async function boot() {
  try {
    setupHourSelectors();
    attachListeners();
    await loadSnapshot();
    await checkPermissions(true);
    await loadCachedReport();

    updateSavedCounts();
    renderHistoryPanel();
    renderSearchPanels();
    if (el.lastAction) {
      el.lastAction.textContent = "Ready";
    }
  } catch (error) {
    if (el.lastAction) {
      el.lastAction.textContent = "Backend unavailable";
    }
    showToast(error.message || "Could not load data.");
  }
})();
