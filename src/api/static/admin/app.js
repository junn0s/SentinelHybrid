const POLL_MS = 3000;

const state = {
  events: [],
  responsesByEventId: new Map(),
  selectedEventId: null,
};

const els = {
  serverStatusDot: document.getElementById("server-status-dot"),
  serverStatusText: document.getElementById("server-status-text"),
  modelText: document.getElementById("model-text"),
  metricEvents: document.getElementById("metric-events"),
  metricResponses: document.getElementById("metric-responses"),
  metricMcpRate: document.getElementById("metric-mcp-rate"),
  metricConfidence: document.getElementById("metric-confidence"),
  eventsMeta: document.getElementById("events-meta"),
  eventTbody: document.getElementById("event-tbody"),
  detailEventId: document.getElementById("detail-event-id"),
  detailRagSource: document.getElementById("detail-rag-source"),
  detailSummary: document.getElementById("detail-summary"),
  detailOperator: document.getElementById("detail-operator"),
  detailTts: document.getElementById("detail-tts"),
  detailReferences: document.getElementById("detail-references"),
  refreshButton: document.getElementById("refresh-button"),
};

function formatTime(isoString) {
  if (!isoString) return "-";
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) return "-";
  return date.toLocaleString("ko-KR", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function safeText(value, fallback = "-") {
  if (value === undefined || value === null || value === "") return fallback;
  return String(value);
}

function updateServerStatus(ok, text) {
  els.serverStatusDot.classList.remove("ok", "fail");
  els.serverStatusDot.classList.add(ok ? "ok" : "fail");
  els.serverStatusText.textContent = text;
}

function calcMetrics(events, responses) {
  const confidences = events
    .map((ev) => ev.confidence)
    .filter((value) => typeof value === "number");
  const avgConfidence =
    confidences.length > 0
      ? (confidences.reduce((acc, value) => acc + value, 0) / confidences.length).toFixed(2)
      : "0.00";

  const mcpCount = responses.filter((res) => res.rag_source === "mcp").length;
  const mcpRate = responses.length > 0 ? `${Math.round((mcpCount / responses.length) * 100)}%` : "0%";

  return {
    eventCount: events.length,
    responseCount: responses.length,
    avgConfidence,
    mcpRate,
  };
}

function renderMetrics(events, responses) {
  const metrics = calcMetrics(events, responses);
  els.metricEvents.textContent = metrics.eventCount;
  els.metricResponses.textContent = metrics.responseCount;
  els.metricMcpRate.textContent = metrics.mcpRate;
  els.metricConfidence.textContent = metrics.avgConfidence;
  els.eventsMeta.textContent = `${metrics.eventCount}건`;
}

function renderEventRows() {
  const rows = state.events;
  if (rows.length === 0) {
    els.eventTbody.innerHTML = `
      <tr>
        <td colspan="4" class="empty-row">이벤트를 기다리는 중입니다.</td>
      </tr>
    `;
    return;
  }

  const html = rows
    .map((event) => {
      const response = state.responsesByEventId.get(event.event_id);
      const rag = response?.rag_source ?? "-";
      const ragClass = rag === "mcp" ? "mcp" : rag === "local-fallback" ? "fallback" : "";
      const selectedClass = state.selectedEventId === event.event_id ? "selected" : "";
      return `
        <tr class="${selectedClass}" data-event-id="${event.event_id}">
          <td>${formatTime(event.timestamp)}</td>
          <td>${safeText(event.source)}</td>
          <td class="summary-cell">${safeText(event.summary)}</td>
          <td class="rag-cell"><span class="tag ${ragClass}">${safeText(rag)}</span></td>
        </tr>
      `;
    })
    .join("");

  els.eventTbody.innerHTML = html;
  els.eventTbody.querySelectorAll("tr[data-event-id]").forEach((row) => {
    row.addEventListener("click", () => {
      state.selectedEventId = row.dataset.eventId;
      renderEventRows();
      renderDetailPanel();
      loadSingleResponseIfNeeded(state.selectedEventId);
    });
  });
}

function renderReferences(references) {
  if (!Array.isArray(references) || references.length === 0) {
    els.detailReferences.innerHTML = `<li class="reference-empty">참고 매뉴얼 없음</li>`;
    return;
  }

  els.detailReferences.innerHTML = references
    .map(
      (ref) => `
        <li class="reference-item">
          <strong>${safeText(ref.title)}</strong>
          <span>${safeText(ref.content)}</span>
        </li>
      `
    )
    .join("");
}

function renderDetailPanel() {
  const selected = state.events.find((ev) => ev.event_id === state.selectedEventId);
  if (!selected) {
    els.detailEventId.textContent = "선택된 이벤트 없음";
    els.detailSummary.textContent = "왼쪽 이벤트를 선택하면 상세가 표시됩니다.";
    els.detailOperator.textContent = "-";
    els.detailTts.textContent = "-";
    els.detailRagSource.textContent = "-";
    renderReferences([]);
    return;
  }

  const response = state.responsesByEventId.get(selected.event_id);
  els.detailEventId.textContent = selected.event_id;
  els.detailSummary.textContent = safeText(selected.summary);
  els.detailOperator.textContent = safeText(response?.operator_response, "응답 생성 대기 중");
  els.detailTts.textContent = safeText(response?.jetson_tts_summary, "-");
  els.detailRagSource.textContent = safeText(response?.rag_source, "pending");
  renderReferences(response?.references ?? []);
}

async function loadSingleResponseIfNeeded(eventId) {
  if (!eventId || state.responsesByEventId.has(eventId)) return;
  try {
    const res = await fetch(`/events/${encodeURIComponent(eventId)}/response`);
    if (!res.ok) return;
    const response = await res.json();
    if (response?.event_id) {
      state.responsesByEventId.set(response.event_id, response);
      renderEventRows();
      renderDetailPanel();
    }
  } catch (_) {
    // Ignore network noise for detail lazy-load.
  }
}

async function loadHealth() {
  try {
    const res = await fetch("/health");
    if (!res.ok) throw new Error(`health ${res.status}`);
    const body = await res.json();
    updateServerStatus(true, "Online");
    els.modelText.textContent = safeText(body.gemini_model || body.llm_provider, "-");
  } catch (_) {
    updateServerStatus(false, "Offline / Error");
    els.modelText.textContent = "-";
  }
}

async function loadRecent() {
  const res = await fetch("/events/recent");
  if (!res.ok) throw new Error(`recent ${res.status}`);
  const body = await res.json();
  const events = Array.isArray(body.events) ? body.events : [];
  const responses = Array.isArray(body.responses) ? body.responses : [];

  state.events = events;
  state.responsesByEventId.clear();
  responses.forEach((item) => {
    if (item?.event_id) {
      state.responsesByEventId.set(item.event_id, item);
    }
  });

  if (!state.selectedEventId && events.length > 0) {
    state.selectedEventId = events[0].event_id;
  } else if (state.selectedEventId && !events.find((ev) => ev.event_id === state.selectedEventId)) {
    state.selectedEventId = events[0]?.event_id ?? null;
  }

  renderMetrics(events, responses);
  renderEventRows();
  renderDetailPanel();
}

async function refreshAll() {
  await Promise.all([loadHealth(), loadRecent()]);
}

function setupActions() {
  els.refreshButton.addEventListener("click", () => {
    refreshAll();
  });
}

async function boot() {
  setupActions();
  await refreshAll();
  window.setInterval(refreshAll, POLL_MS);
}

boot();
