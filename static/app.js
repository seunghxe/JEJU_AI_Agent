/* 제주 EV Plan B AI – 화면 로직 */
const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const state = {
  meta: null, view: "recommend", current: null, history: [], favorites: [], points: [], chargeHistory: null,
  liveATone: null, threadId: null, batteryDirty: false,
  s: { connector: "", vehicle: null, battery: 40, origin: "", origin_lat: null, origin_lon: null, preference: "균형 추천" },
};

/* ---------------- 아이콘 ---------------- */
const PIN_IN = (fill, stroke = "#fff") => `<path d="M15 37s13-12.2 13-22A13 13 0 0 0 2 15c0 9.8 13 22 13 22z" fill="${fill}" stroke="${stroke}" stroke-width="2.5"/><circle cx="15" cy="15" r="5" fill="${fill === "#fff" ? "#2F6BFF" : "#fff"}"/>`;
const PIN = (fill) => `<svg viewBox="0 0 30 38">${PIN_IN(fill)}</svg>`;
const ICON = {
  bolt: `<svg viewBox="0 0 24 24"><path d="M13 2L4 14h7l-1 8 9-12h-7z"/></svg>`,
  route: `<svg viewBox="0 0 24 24"><circle cx="4" cy="17" r="2.5"/><circle cx="18" cy="6" r="2.5"/><path d="M8.5 17H14a3 3 0 0 0 0-6h-4a3 3 0 0 1 0-6h5.5"/></svg>`,
  station: `<svg viewBox="0 0 24 24"><rect x="4" y="4" width="10" height="16" rx="1.5"/><path d="M4 10h10M14 8h2a2 2 0 0 1 2 2v6a1.5 1.5 0 0 0 3 0V9l-2-3"/><path d="M8 13l-1 2h3l-1 2"/></svg>`,
  fast: `<svg viewBox="0 0 24 24"><path d="M13 2L4 14h7l-1 8 9-12h-7z"/></svg>`,
  batt: `<svg viewBox="0 0 24 24"><rect x="2" y="7" width="17" height="10" rx="2"/><path d="M21 10v4M7 12l2 2 4-4"/></svg>`,
};

/* ---------------- 설정 ---------------- */
function loadSettings() {
  try { Object.assign(state.s, JSON.parse(localStorage.getItem("planb.v6") || "{}")); } catch (e) { /* 없음 */ }
  try { state.history = JSON.parse(localStorage.getItem("planb.v6.history") || "[]").slice(-10); } catch (e) { state.history = []; }
  try { state.favorites = JSON.parse(localStorage.getItem("planb.last2.favorites") || "[]").slice(0, 12); } catch (e) { state.favorites = []; }
  state.threadId = localStorage.getItem("planb.v7.thread") || newThreadId();
  localStorage.setItem("planb.v7.thread", state.threadId);
  state.s.origin_lat = null; state.s.origin_lon = null;
}
function newThreadId() {
  return (window.crypto && crypto.randomUUID) ? crypto.randomUUID() : `planb-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}
async function newConversation() {
  const old = state.threadId;
  state.threadId = newThreadId();
  localStorage.setItem("planb.v7.thread", state.threadId);
  state.current = null; state.liveATone = null; hideSwitchToast();
  if (old) fetch(`/api/conversation/${encodeURIComponent(old)}`, { method: "DELETE" }).catch(() => {});
}
function saveSettings() {
  try { const { vehicle, battery, origin, preference, connector } = state.s; localStorage.setItem("planb.v6", JSON.stringify({ vehicle, battery, origin, preference, connector })); } catch (e) { /* 저장 불가 */ }
}
function saveHistory() {
  try { localStorage.setItem("planb.v6.history", JSON.stringify(state.history.slice(-10))); } catch (e) { /* 저장 불가 */ }
}
function saveFavorites() {
  try { localStorage.setItem("planb.last2.favorites", JSON.stringify(state.favorites.slice(0, 12))); } catch (e) { /* 저장 불가 */ }
}
const vehicle = () => state.meta.vehicles.find((v) => v.name === state.s.vehicle) || state.meta.vehicles[0];
const rangeKm = () => Math.round((vehicle().kwh * vehicle().eff * state.s.battery) / 100);
function decorateSettings(){
  const paths={car:'M3 16v-5l3-5h10l4 5v5H3m3 0v3m11-3v3M5 11h13',sliders:'M3 6h8m4 0h6M3 12h2m4 0h12M3 18h10m4 0h4M11 3v6M7 9v6m8 0v6',balance:'M12 4v16M4 8l8-3 8 3M5 9l-3 6h6l-3-6Zm14 0-3 6h6l-3-6ZM8 21h8',time:'M12 4a8 8 0 1 0 .1 0ZM12 8v5l4 2',wait:'M6 3h12M6 21h12M7 4c0 5 2 6 5 8-3 2-5 3-5 8m10-16c0 5-2 6-5 8 3 2 5 3 5 8',backup:'M5 21v-5c0-4 6-4 6-9V3m-4 4 4-4 4 4M6 14c5-1 10 0 12-5m-4 0h4v4'};
  $$("[data-glyph]").forEach(el=>{el.innerHTML='<svg aria-hidden="true" viewBox="0 0 24 24"><path d="'+paths[el.dataset.glyph]+'"/></svg>';});
}
// Real model photographs; credit + original and license stay next to each image.
const carPhotos = {
  "현대 코나 일렉트릭":["0_Hyundai_Kona_Electric_(OS)_0.jpg","3/3f","Benespit"],
  "현대 아이오닉 5":["0_Hyundai_Ioniq_5.jpg","8/8e","Benespit"],
  "기아 니로 EV":["0_Kia_Niro_EV_(SG2)_1.jpg","1/15","Benespit"],
  "기아 EV6":["0_Kia_EV6_0.jpg","f/fc","Benespit"],
  "테슬라 모델 3":["Tesla_Model_3_Front_View.jpg","b/b7","Ominae"],
  "르노 조에":["White_Renault_Zoe_(front).jpg","7/7a","Fiver, der Hellseher"]
};
function renderCarPhoto(name){
  const el=$("#carArt"); if(el.dataset.model===name)return;el.dataset.model=name;
  const photo=carPhotos[name];
  if(!photo){el.innerHTML='<div class="garage-empty">직접 설정한 전기차 · 대표 사진 없음</div>';return;}
  const [filename,path,author]=photo, file=encodeURIComponent(filename), source="https://commons.wikimedia.org/wiki/File:"+file;
  const host=name==="현대 코나 일렉트릭"?"upload.wikimedia.org":"thumb.wikimedia.org";
  el.innerHTML=`<figure><div class="car-frame"><img alt="${esc(name)} 실물 사진" decoding="async" referrerpolicy="no-referrer"></div><figcaption><a href="${source}" target="_blank" rel="noopener">사진 · ${esc(author)} ↗</a><a href="https://creativecommons.org/licenses/by-sa/4.0/" target="_blank" rel="noopener">CC BY-SA 4.0</a></figcaption></figure>`;
  const img=el.querySelector("img"); img.onerror=()=>{img.parentElement.textContent="사진을 불러오지 못했어요";};img.src="https://"+host+"/wikipedia/commons/thumb/"+path+"/"+file+"/330px-"+file;
}
function renderCar() {
  renderCarPhoto(vehicle().name);$("#garageName").textContent=vehicle().name;
  $("#vehicleSel").value = vehicle().name;
  $("#customConnectorBox").hidden = !vehicle().name.includes("기타");
  $("#connectorSel").value = state.s.connector || "";
  $("#connectorHint").textContent = !state.s.connector || state.s.connector === "모름"
    ? "차량 설명서 또는 충전구 표기를 확인해 주세요. 현재 추천 데이터는 DC콤보·50kW 이상 시설입니다."
    : state.s.connector === "DC콤보" ? "DC콤보·50kW 이상 시설 중에서 Plan A와 Plan B를 추천합니다."
    : "현재 데이터는 DC콤보·50kW 이상 시설이므로 선택한 규격의 호환 추천을 제공할 수 없습니다.";
  $("#battRange").value = state.s.battery;
  $("#battRange").style.setProperty("--p", `${((state.s.battery - 5) / 95) * 100}%`);
  $("#battPct").textContent = `${state.s.battery}%`;
  $("#battPct").style.color = state.s.battery <= 20 ? "var(--red)" : state.s.battery <= 35 ? "var(--amber)" : "var(--ink)";
  $("#rangeKm").textContent = `${rangeKm()}km`;
  $("#settingsSummary").textContent = `${vehicle().name} · ${state.s.battery}% · 약 ${rangeKm()}km`;
  $("#originInput").value = state.s.origin_lat != null ? "내 위치" : state.s.origin;
  const modes={"균형 추천":"거리·운영기록·대체 여유를 함께 비교합니다.","이동시간 우선":"주변 후보 중 도로시간이 짧은 곳. 경로 미확인 시 직선거리로 비교합니다.","대기 위험 우선":"과거 충전 이력 등으로 추정한 혼잡 위험이 낮은 곳부터 비교합니다.","Plan B 우선":"이용 가능한 대안 여부와 대안까지의 거리를 우선합니다."};
  if(!modes[state.s.preference]) state.s.preference="균형 추천";
  $("#prefSummary").textContent=state.s.preference; $("#prefHint").textContent=modes[state.s.preference];
  $$("#prefTiles button").forEach(b=>{const on=b.dataset.v===state.s.preference;b.classList.toggle("on",on);b.setAttribute("aria-pressed",String(on));});
}

/* ---------------- 연결 상태 ---------------- */
function hubStatusSummary(hub = {}) {
  const count = Object.values(hub.loaded || {}).filter(n => Number(n) > 0).length;
  if (count && hub.mode === "snapshot") return `저장 자료 사용 · 데이터 ${count}종`;
  if (count) return `${Object.keys(hub.errors || {}).length ? "일부 연동" : "연동됨"} · 데이터 ${count}종`;
  if (hub.state === "ready") return "데이터 준비 중";
  if (hub.state === "error") return "연결 확인 필요 · 과거 기록 사용";
  return "미연동 · 동봉 과거 기록 사용";
}
function renderStatus(st) {
  if (state.meta) state.meta.status = st;
  $("#liveDot").className = "sdot " + st.live.state;
  $("#liveLabel").textContent = st.live.state === "on" ? `실시간 ${st.live.text}` : st.live.state === "error" ? "실시간 연결 오류" : "실시간 꺼짐 · 과거 기록 기준";
  $("#heroChip").textContent = st.live.state === "on" ? `● 실시간 충전기 상태 ${st.live.text.split(" ")[0]} 기준` : "● 과거 관측 기록 기준 안내";
  const memory = { state: "on", text: (state.meta && state.meta.orchestration ? state.meta.orchestration.memory : "세션 기억") };
  const rows = [["대화 맥락·상태 관리", "LangGraph", memory], ["실시간 충전기 상태", "한국환경공단 API", st.live],
    ["과거 이용 데이터", "제주데이터허브", { ...(st.datahub || {state:"off"}), text:hubStatusSummary(st.datahub) }],
    ["자연어 이해 · 답변", "Google Gemini", st.gemini], ["장소·자동차 경로", "Kakao API", st.kakao]];
  $("#connList").innerHTML = rows.map(([t, s, v]) => `<li><span class="sdot ${v.state}"></span><div><b>${t}</b><small>${s} · ${esc(v.text)}</small></div></li>`).join("");
  const hub = st.datahub || {}, labels = {weekly:"요일별 충전 이력",daily:"일별 충전 이력",wait:"일별 대기시간",floating:"읍면동 유동인구"};
  const panel = $("#connList").children[2]?.querySelector("div");
  const kinds = [...new Set([...(hub.configured_datasets || []), ...Object.keys(hub.loaded || {})])];
  if (!panel || !kinds.length) return;
  const details = document.createElement("details");
  details.className = "hub-status-details";
  const summary = document.createElement("summary");
  summary.textContent = "데이터 상세 보기";
  details.appendChild(summary);
  for (const kind of kinds) {
    const line = document.createElement("small"), d = hub.details?.[kind] || {};
    const error = hub.errors?.[kind];
    line.style.display = "block";
    line.textContent = error || (d.matched ? `${labels[kind]}: ${d.rows}행 → 원본 ${d.raw_unique}곳 → 연결 ${d.matched}곳 (${d.bundled?"동봉 집계":d.cached?"저장 집계":"조회 기간 전체"})` : `${labels[kind]}: ${d.rows ? d.rows+"행 수신 중" : "확인 대기"}`);
    details.appendChild(line);
  }
  panel.appendChild(details);
}

/* ---------------- 지도 ---------------- */
let dotsRenderer, map, dots, layer, routeZoomControl, overviewActive = true;
const JEJU_BOUNDS = [[33.17, 126.10], [33.57, 126.98]];
const TONE = { good: "#16B37A", warn: "#E88A12", bad: "#E5484D", muted: "#A3ABBC" };
function initMap() {
  map = L.map("map", { zoomControl: false, zoomSnap: 0.5 }).setView([33.37, 126.55], 10);
  L.control.zoom({ position: "topright" }).addTo(map);
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19, attribution: "&copy; OpenStreetMap contributors" }).addTo(map);
  dotsRenderer = L.canvas({padding:.3, tolerance:5}).addTo(map);
  dots = L.layerGroup().addTo(map);
  layer = L.layerGroup().addTo(map);
  fitJeju(false);
  map.on("zoomend", () => { if (overviewActive) renderOverviewDots(); });
  new ResizeObserver(() => map.invalidateSize()).observe($("#map"));
}
async function loadPoints() {
  state.points = await fetch("/api/stations").then((r) => r.json());
  renderOverviewDots();
  if (state.view === "map") renderView();
}
function renderOverviewDots() {
  if(KakaoView.ready){if(overviewActive)KakaoView.stations();return;}
  if (!map || !state.points.length || !overviewActive) return;
  dots.clearLayers();
  const zoom = map.getZoom();
  const renderer = dotsRenderer;
  if (zoom >= 12) {
    state.points.forEach(([lat, lon, name, tone, detail]) => {
      L.circleMarker([lat, lon], { renderer, radius: tone === "bad" ? 5 : 4, weight: 1.5, color: "#fff", fillColor: TONE[tone] || TONE.muted, fillOpacity: 0.92 })
        .bindPopup(infoPopup(name, detail)).bindTooltip(esc(name), { className: "small", direction: "top" }).addTo(dots);
    });
    return;
  }
  const cell = zoom <= 9 ? 72 : zoom === 10 ? 60 : 48;
  const groups = new Map();
  state.points.forEach((p) => {
    const pt = map.project([p[0], p[1]], zoom);
    const key = `${Math.floor(pt.x / cell)}:${Math.floor(pt.y / cell)}`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(p);
  });
  groups.forEach((items) => {
    const lat = items.reduce((s, p) => s + p[0], 0) / items.length;
    const lon = items.reduce((s, p) => s + p[1], 0) / items.length;
    const bad = items.filter((p) => p[3] === "bad").length;
    const warn = items.filter((p) => p[3] === "warn").length;
    const tone = bad >= Math.max(2, items.length * .2) ? "bad" : (warn + bad >= Math.max(2, items.length * .25) ? "warn" : "good");
    if (items.length === 1) {
      const p = items[0];
      L.circleMarker([p[0], p[1]], { renderer, radius: p[3] === "bad" ? 5 : 4, weight: 1.5, color: "#fff", fillColor: TONE[p[3]] || TONE.muted, fillOpacity: .92 })
        .bindPopup(infoPopup(p[2],p[4])).bindTooltip(esc(p[2]), { className: "small", direction: "top" }).addTo(dots);
      return;
    }
    const size = Math.min(44, 27 + Math.log2(items.length) * 4);
    const icon = L.divIcon({ className: "", iconSize: [size, size], iconAnchor: [size / 2, size / 2],
      html: `<span class="map-cluster ${tone}" style="width:${size}px;height:${size}px">${items.length}</span>` });
    L.marker([lat, lon], { icon, keyboard: true, title: `${items.length}개 충전시설` })
      .bindTooltip(`${items.length}개 충전시설 · 눌러서 확대`, { className: "small", direction: "top" })
      .on("click", () => map.flyTo([lat, lon], Math.min(13, zoom + 2), { duration: .45 })).addTo(dots);
  });
}
function infoPopup(name,d={}) {
  const live=d.live, tone=["good","warn","bad"].includes(live?.tone)?live.tone:"muted";
  return `<article class="station-info"><small>급속 충전소</small><h3>${esc(name)}</h3><div class="st-address">${esc(d.address || "주소 미확인")}</div><div class="st-metrics"><div><small>설치 규모</small><b>${esc(d.chargers ?? "—")}기</b></div><div><small>현재 상태</small><b class="st-${tone}">${esc(live?.text || "미확인")}</b></div></div><dl><dt>과거 운영</dt><dd>${esc(d.reliability?.text || "기록 부족")}</dd>${d.backup?`<dt>대체 후보</dt><dd>${esc(d.backup)}</dd>`:""}</dl>${d.directions?`<a target="_blank" rel="noopener" href="${esc(d.directions)}">카카오맵 길찾기 <span>↗</span></a>`:""}</article>`;
}
function setLegend(mode, routes = {}) {
  const liveOn = state.meta && state.meta.status.live.state === "on";
  $("#legend").innerHTML = mode === "result"
    ? `${routes.a ? '<div><span class="ln"></span>Plan A 주행 경로</div>' : ""}
       ${routes.b ? '<div><span class="ln" style="background:repeating-linear-gradient(90deg,#087D75 0 6px,transparent 6px 10px)"></span>Plan B 주행 경로</div>' : ""}
       <div>${PIN("var(--blue)")}Plan A (추천 충전소)</div>
       ${routes.hasB ? `<div>${PIN("#087D75")}Plan B (대체 충전소)</div>` : ""}
       ${routes.hasDest ? '<div><span class="dt" style="border:2px solid #2F6BFF"></span>목적지</div>' : ""}`
    : `<div><span class="dt" style="background:#19A979"></span>양호</div><div><span class="dt" style="background:#E88A12"></span>주의</div><div><span class="dt" style="background:#E5484D"></span>이용 곤란</div><small>숫자는 시설 수 · 확대 후 점을 눌러 상세 보기</small>`;
}
function fitJeju(animate) {
  map.fitBounds(JEJU_BOUNDS, { padding: [32, 36], maxZoom: 11.5, animate });
}

function overview() {
  overviewActive = true;
  if(KakaoView.ready){setLegend("overview");$("#mapChip").textContent="📍 제주도 전체";KakaoView.overview();return;}
  if (routeZoomControl) {
    routeZoomControl.remove();
    routeZoomControl = null;
  }
  layer.clearLayers();
  setLegend("overview");
  $("#mapChip").textContent = "📍 제주도 전체";
  fitJeju(true);
  renderOverviewDots();
}

function stationPin(station, letter, color) {
  const backup = letter === "B";
  const pin = PIN_IN(color);
  const icon = L.divIcon({
    className: "",
    html: `<svg viewBox="0 0 30 38" width="26" height="33" aria-hidden="true">
      <g${backup ? ' transform="translate(0 38) scale(1 -1)"' : ""}>${pin}</g>
      <text x="15" y="${backup ? 26 : 18}" text-anchor="middle" fill="${color}" font-size="8" font-weight="800">${letter}</text>
    </svg>`,
    iconSize: [26, 33],
    iconAnchor: backup ? [13, 1] : [13, 32],
    tooltipAnchor: backup ? [0, 24] : [0, -25],
    popupAnchor: backup ? [0, 10] : [0, -26],
  });
  const name = `Plan ${letter} · ${station.name}`;
  return L.marker([station.lat, station.lon], { icon, title: name, alt: name, riseOnHover: true })
    .bindTooltip(esc(name), { className: "small", direction: backup ? "bottom" : "top" })
    .bindPopup(infoPopup(name, station))
    .addTo(layer);
}

function fitRoute(points, maxZoom) {
  const compact = map.getSize().x < 640;
  map.flyToBounds(L.latLngBounds(points), {
    paddingTopLeft: compact ? [28, 64] : [55, 70],
    paddingBottomRight: compact ? [28, 48] : [55, 78],
    maxZoom,
    duration: 0.55,
  });
}

function showRouteZoom(fullPoints, stationPoints) {
  if (routeZoomControl) routeZoomControl.remove();
  routeZoomControl = L.control({ position: "bottomleft" });
  routeZoomControl.onAdd = () => {
    const container = L.DomUtil.create("div", "leaflet-bar");
    for (const [label, points, maxZoom] of [
      ["전체 경로", fullPoints, 14],
      ["충전소 확대", stationPoints, 17],
    ]) {
      const button = L.DomUtil.create("button", "", container);
      button.type = "button";
      button.textContent = label;
      Object.assign(button.style, { background: "#fff", color: "#182338", border: "0", padding: "7px 10px", cursor: "pointer" });
      button.addEventListener("click", () => fitRoute(points, maxZoom));
    }
    L.DomEvent.disableClickPropagation(container);
    return container;
  };
  routeZoomControl.addTo(map);
}

function drawResult(res) {
  overviewActive = false;
  dots.clearLayers();
  layer.clearLayers();
  $("#mapChip").textContent = `📍 ${res.dest.name} 주변`;
  const A = res.A, B = res.B, D = res.dest;
  const stationPoints = [[A.lat, A.lon]];
  const aRoute = A.driving?.coordinates || [];
  const bRoute = B?.driving?.coordinates || [];
  const hasB = B?.lat != null && B?.lon != null;
  const sameSpot = Math.abs(D.lat - A.lat) + Math.abs(D.lon - A.lon) < 0.00005;
  setLegend("result", { a: aRoute.length > 1, b: bRoute.length > 1, hasB, hasDest: !sameSpot });
  if(KakaoView.ready){KakaoView.result(res);return;}
  res.alternatives.forEach((s) => L.marker([s.lat, s.lon], { icon: L.divIcon({ className: "", html: `<div class="mkalt"></div>`, iconSize: [0, 0] }) })
    .bindPopup(infoPopup(s.name,s)).bindTooltip(esc(s.name), { className: "small" }).addTo(layer));
  if (aRoute.length > 1) {
    L.polyline(aRoute, { color: "#2F6BFF", weight: 6, opacity: 0.85, lineCap: "round" }).addTo(layer);
  }
  if (hasB) {
    if (bRoute.length > 1) {
      L.polyline(bRoute, { color: "#087D75", weight: 5, dashArray: "5 8", lineCap: "round" }).addTo(layer);
    }
    stationPin(B, "B", "#087D75");
    stationPoints.push([B.lat, B.lon]);
  }
  if (!sameSpot) {
    const name = `목적지 · ${D.name}`;
    L.circleMarker([D.lat, D.lon], { radius: 6, color: "#2F6BFF", fillColor: "#fff", fillOpacity: 1, weight: 2 })
      .bindTooltip(esc(name), { className: "small", direction: "bottom" })
      .bindPopup(esc(name)).addTo(layer);
  }
  stationPin(A, "A", "#2F6BFF");
  const fullPoints = stationPoints.concat(aRoute, bRoute, [[D.lat, D.lon]]);
  if (res.origin) {
    const name = `출발 · ${res.origin.name}`;
    L.circleMarker([res.origin.lat, res.origin.lon], { radius: 6, color: "#5B6478", fillColor: "#fff", fillOpacity: 1, weight: 2 })
      .bindTooltip(esc(name), { className: "small", direction: "right" })
      .bindPopup(esc(name)).addTo(layer);
    fullPoints.push([res.origin.lat, res.origin.lon]);
  }
  showRouteZoom(fullPoints, stationPoints);
  fitRoute(fullPoints, 14);
}

/* ---------------- 오른쪽 패널 ---------------- */
const head = (t) => `<h2 class="rh">${ICON.bolt}${t}</h2>`;
function badge(t, cls) { return t ? `<span class="bd ${cls || t.tone}">${esc(t.text || t)}</span>` : ""; }
function welcome() {
  const ex = [
    ["⛰️", "내일 어리목에서 한라산 탐방해. 배터리 30%야", "대안이 적은 구간은 미리 알려드려요"],
    ["🌅", "성산일출봉 가는데 근처 충전소 알려줘", "가까우면서 지금 비어 있는 곳"],
    ["🔁", "애월읍 충전소가 막히면 어디로 가?", "막혔을 때 갈 Plan B까지"],
  ].map(([i, q, s]) => `<button class="ex" data-q="${esc(q)}"><i>${i}</i><span>${esc(q)}<small>${s}</small></span></button>`).join("");
  const liveOn = state.meta && state.meta.status.live.state === "on";
  const basis = liveOn ? "현재 상태와 평소 운영기록을 함께 확인한 급속충전소" : "과거 운영기록이 안정적인 급속충전소";
  return head("AI 충전소 추천") + `<p class="lead">가는 곳이나 여행 상황을 위 검색창에 적어 주세요. 근처에서 <b>${basis}(Plan A)</b>와 <b>막혔을 때 갈 곳(Plan B)</b>을 함께 찾아드려요.</p>
    <div class="sec">이렇게 물어보세요</div>${ex}
    <div class="sec">이렇게 골라요</div>
    <div class="steps3">
      <div><i style="background:var(--blue)">A</i><span><b>가깝고 평소 잘 되는 곳</b><p>2주간 5분마다 기록한 운영 상태${liveOn ? " + 현재 상태" : ""}</p></span></div>
      <div><i style="background:var(--teal)">B</i><span><b>A가 막혔을 때 갈 곳</b><p>거리·급속충전기 수·배터리로 갈 수 있는지</p></span></div>
      <div><i style="background:var(--amber)">!</i><span><b>대안이 적은 구간 경고</b><p>한라산 탐방로처럼 대안이 먼 곳은 출발 전 충전</p></span></div>
      <div><i style="background:#7557D9">↻</i><span><b>후속 요청까지 기억</b><p>“Plan A는 빼고 다시”처럼 이어서 물어보세요</p></span></div>
    </div>`;
}
function routeText(driving, straightKm) {
  if (driving?.source === "same_location") return "같은 위치 · 0km";
  if (driving) return `차로 약 ${driving.minutes}분 · ${driving.distance_km.toFixed(1)}km`;
  return straightKm == null
    ? "차량 경로 미확인"
    : `직선 ${straightKm.toFixed(1)}km · 차량 경로 미확인`;
}
let chargeHistoryRequest;
function loadChargeHistory() {
  chargeHistoryRequest ??= fetch("/static/charge_history.json").then(async (response) => {
    if (!response.ok) throw new Error("충전 이력 파일을 불러오지 못했습니다.");
    const data = await response.json();
    if (!data.stations || typeof data.stations !== "object" || Array.isArray(data.stations)) {
      throw new Error("충전 이력 파일의 형식이 올바르지 않습니다.");
    }
    state.chargeHistory = data.stations;
  }).catch(() => {
    chargeHistoryRequest = null;
  });
  return chargeHistoryRequest;
}
function chargeHistoryBadge(station) {
  const serverHistory = station.history;
  if (serverHistory) {
    const tone = serverHistory.level === "high" ? "warn" : serverHistory.level === "low" ? "good" : "muted";
    const detail = Array.isArray(serverHistory.evidence) && serverHistory.evidence.length
      ? serverHistory.evidence.join(" · ")
      : (serverHistory.peak_hours || []).map((hour) => `${hour}시대`).join(" · ");
    return `<div class="badges history"><span class="bd ${tone}">${esc(serverHistory.text)}</span><small>${esc(detail)} · 신뢰도 ${esc(serverHistory.confidence || "참고")} · ${esc(serverHistory.source)}</small></div>`;
  }
  const record = state.chargeHistory?.[station.id];
  const hours = record?.peak_hours;
  if (!Array.isArray(hours) || !hours.length) {
    return state.chargeHistory ? "" : `<div class="badges"><span class="bd muted">과거 충전 이력 불러오기 실패</span></div>`;
  }
  const time = hours.map((hour) => `${hour}시대`).join(" · ");
  const period = record.first_month === record.last_month
    ? record.first_month
    : `${record.first_month}~${record.last_month}`;
  return `<div class="badges history"><span class="bd muted">과거 충전 시작 최다 ${esc(time)} (${esc(period)})</span></div>`;
}
function resultHtml(res) {
  const saved = res.ok && state.favorites.some((f) => f.name === res.dest.name);
  const actions = `<div class="plan-tools">${res.ok ? `<button data-save>${saved ? "✓ 저장됨" : "☆ 목적지 저장"}</button>` : ""}<button data-reset>새 대화</button></div>`;
  const detailHead=(icon,title,caption)=>`<summary><i aria-hidden="true">${icon}</i><span><b>${title}</b><small>${caption}</small></span></summary>`;
  const chips=res.ok ? [res.dest.name, res.preference,`배터리 ${res.battery}%`].filter(Boolean) : [];
  const back = `<details class="trip-detail trip-fold question-fold">${detailHead(ICON.route,"내 요청 보기","보낸 질문과 반영된 조건")}<div class="fold-body"><div class="fold-label">내가 보낸 질문</div><blockquote>${esc(res.query)}</blockquote>${chips.length?`<div class="condition-chips">${chips.map(c=>`<span>${esc(c)}</span>`).join("")}</div>`:""}</div></details>`;
  if (!res.ok) return head(res.clarify ? "한 가지만 알려주세요" : "추천 안내") + `<section class="trip-brief"><small>${res.clarify?"목적지 확인":"차량 조건 확인"}</small><p>${esc(res.summary)}</p></section>` + (res.clarify ? `<form class="place-retry"><label for="retryName">답장 · 배터리 ${esc(res.battery)}% 유지</label><div><input id="retryName" maxlength="80" required placeholder="예: 애월읍이야 / 협재해수욕장 근처"><button>답장 보내기</button></div></form>` : "") + back + actions;
  const A = res.A, B = res.B;
  let say = esc(res.summary);
  res.highlight.forEach((n) => { if (n) say = say.split(esc(n)).join(`<b>${esc(n)}</b>`); });
  const aStart = res.origin || res.dest;
  const dist = routeText(A.driving, A.route_straight_km);
  const aReach = A.reach ? (A.reach.ok ? "이동 가능" : "확인 필요") : "출발지 미입력";
  const aCard = `<article class="pcard a">
    <div class="ph"><svg class="pinic" viewBox="0 0 30 38">${PIN_IN("#2F6BFF")}</svg><span class="tt">Plan A</span><span class="nm">${esc(A.name)}</span>
      <a href="${A.directions}" target="_blank" rel="noopener" aria-label="A 길찾기">›</a></div>
    <div class="badges"><span class="bd score">★ 추천 1순위</span>
      ${badge(A.reliability)}${A.live ? badge(A.live) : `<span class="bd muted">실시간 미확인</span>`}</div>
    <div class="facts col">
      <div><span class="fh">${ICON.route}${esc(aStart.name)}에서</span><b>${dist}</b></div>
      <div><span class="fh">${ICON.fast}급속</span><b>${A.chargers}기</b></div>
      <div><span class="fh">${ICON.batt}현재 배터리로</span><b class="${A.reach && !A.reach.ok ? "no" : A.reach ? "ok" : ""}">${aReach}</b></div>
    </div>
    ${chargeHistoryBadge(A)}
  </article>`;
  const bDistance = B ? routeText(B.driving, B.from_a_km) : "";
  const bCard = B ? `<article class="pcard b">
    <div class="ph"><svg class="pinic" viewBox="0 0 30 38">${PIN_IN("#12A39A")}</svg><span class="tt">Plan B</span><span class="nm">${esc(B.name)}</span>
      <a href="${B.directions}" target="_blank" rel="noopener" aria-label="B 길찾기">›</a></div>
    <div class="badges">${badge(B.reliability)}${B.live ? badge(B.live) : `<span class="bd muted">실시간 미확인</span>`}</div>
    <div class="facts col">
      <div><span class="fh">${ICON.route}Plan A에서</span><b>${bDistance}</b></div>
      <div><span class="fh">${ICON.fast}급속</span><b>${B.chargers}기</b></div>
      <div><span class="fh">${ICON.batt}${B.reach ? "현재 배터리로" : "배터리"}</span><b class="${B.reach && !B.reach.ok ? "no" : "ok"}">${B.reach ? (B.reach.ok ? "이동 가능" : "확인 필요") : "미확인"}</b></div>
    </div>
    ${chargeHistoryBadge(B)}
  </article>` : `<div class="note warn">⚠️ <span>${esc(res.plan_b_search?.message || "가까운 곳에 독립적인 대체 충전소가 없어요. 출발 전에 충분히 충전하세요.")}</span></div>`;
  const notes = res.notes.map((n) => `<div class="note ${n.tone}">${n.tone === "ok" ? "🔋" : n.tone === "info" ? "ℹ️" : "⚠️"}<span>${esc(n.text)}</span></div>`).join("");
  const alts = res.alternatives.length ? `<details><summary>다른 후보 ${res.alternatives.length}곳</summary>${res.alternatives.map((s) =>
    `<div class="alt"><div><b>${esc(s.name)}</b><small>${s.from_dest_km != null ? s.from_dest_km.toFixed(1) + "km · " : ""}급속 ${s.chargers}기 · ${esc(s.reliability.text)}${s.live ? " · " + esc(s.live.text) : ""}</small></div>
     <a href="${s.directions}" target="_blank" rel="noopener">길찾기 ›</a></div>`).join("")}</details>` : "";
  const evidence=[
    ["선택 기준",res.preference,res.basis],
    ["운영 상태",A.live?.text || "실시간 미확인","과거 기록: "+(A.reliability?.text || "자료 없음")],
    ["대체 충전소",B?.name || "확인된 대안 없음",B?bDistance:"출발 전 다른 충전 경로를 확인해 주세요."],
  ];
  const why=`<details class="trip-detail trip-fold reason-fold">${detailHead(ICON.bolt,"추천 이유 보기","선택 기준과 충전소 상태")}<div class="fold-body"><dl class="evidence-list">${evidence.map(([label,value,note])=>`<div><dt>${esc(label)}</dt><dd><strong>${esc(value)}</strong><small>${esc(note)}</small></dd></div>`).join("")}</dl><div class="fold-label">추천 설명</div><p class="reason-copy">${say}</p></div></details>`;
  const oldTurns = (res.conversation || []).slice(0, -2);
  const history = oldTurns.length ? `<details class="chat-history"><summary>이전 대화 ${Math.floor(oldTurns.length / 2)}턴 보기</summary>${oldTurns.map((t) => `<div class="chatline ${t.role}"><b>${t.role === "user" ? "사용자" : "AI"}</b><span>${esc(t.text)}</span></div>`).join("")}</details>` : "";
  const followups = `<div class="followups"><span>조건을 바꿔 다시 찾기</span><button data-q="Plan A는 빼고 다시 찾아줘">Plan A 제외</button><button data-q="대기 위험이 더 낮은 곳으로 찾아줘">대기 위험 낮게</button><button data-q="이동시간 짧게 다시 찾아줘">이동시간 짧게</button><button data-q="Plan B가 더 안전한 곳으로 찾아줘">Plan B 안전하게</button></div>`;
  const brief = `<section class="trip-brief"><small>목적지 기준 충전 계획</small><h3>${esc(res.dest.name)}</h3><p>${esc(res.dest.address || res.dest.source)} · 배터리 ${esc(res.battery)}%</p><div class="trip-mode">${esc(res.preference)}</div></section>`;
  return brief + actions + aCard + bCard +
    `<a class="bigbtn" href="${A.directions}" target="_blank" rel="noopener"><svg viewBox="0 0 30 38">${PIN_IN("#fff", "none")}</svg>카카오맵으로 길찾기 <span>›</span></a>` +
    (B ? `<a class="subbtn" href="${B.directions}" target="_blank" rel="noopener">Plan B로 길찾기</a>` : "") + followups + notes + why + back + history + alts;
}
function mapPanel() {
  const c = { good: 0, warn: 0, bad: 0, muted: 0 };
  state.points.forEach((p) => { c[p[3]] = (c[p[3]] || 0) + 1; });
  const liveOn = state.meta && state.meta.status.live.state === "on";
  return head("제주 충전망 한눈에") + `<p class="lead">숫자 원은 주변 시설 수를 나타내고, 확대하면 ${liveOn ? "현재 상태와 과거 운영기록을" : "2주간 5분마다 기록한 운영 상태를"} 반영한 개별 시설이 나타나요.</p>
    <div class="statgrid"><div><b>${state.points.length || "-"}</b><span>급속충전시설</span></div><div><b style="color:${TONE.good}">${c.good}</b><span>평소 잘 운영됨</span></div>
    <div><b style="color:${TONE.warn}">${c.warn}</b><span>가끔 이용 불가</span></div><div><b style="color:${TONE.bad}">${c.bad}</b><span>자주 이용 불가</span></div></div>
    <div class="note info">ℹ️<span>점을 누르면 주소, 상태, 대체 후보가 보여요. 가는 곳을 검색하면 그 주변 Plan A·B를 골라 드려요.</span></div>`;
}
function tripsPanel() {
  if (!state.history.length) return head("내 여행 계획") + `<div class="empty">아직 찾아본 곳이 없어요. 위 검색창에 가는 곳을 적어 보세요.</div>`;
  return head("최근 충전 계획") + `<p class="lead">최근 찾아본 충전 계획을 이 브라우저에 최대 10개 저장해요.</p>` +
    state.history.slice().reverse().map((h, i) => {
      const idx = state.history.length - 1 - i, r = h.result;
      return `<button class="ex" data-h="${idx}"><i>${r.ok ? "📍" : "❔"}</i><span>${esc(r.ok ? r.dest.name : h.query)}<small>${r.ok ? `A ${esc(r.A.name)}${r.B ? ` · B ${esc(r.B.name)}` : ""}` : esc(h.query)}</small></span></button>`;
    }).join("");
}
function placesPanel() {
  const icons = { "성산일출봉": "🌅", "한라산 어리목": "⛰️", "협재해수욕장": "🏖️", "중문관광단지": "🏨", "함덕해수욕장": "🌊", "우도": "⛴️" };
  if (!state.favorites.length) return head("자주 가는 곳") + `<p class="lead">추천 결과에서 목적지를 저장하면 여기에 모아둘 수 있어요. 먼저 대표 장소로 시험해 보세요.</p>` +
    state.meta.quick.slice(0, 4).map((p) => `<button class="ex" data-q="${esc(p.query)}"><i>${icons[p.label] || "📍"}</i><span>${esc(p.label)}<small>Plan A·B 바로 찾기</small></span></button>`).join("");
  return head("자주 가는 곳") + `<p class="lead">저장한 목적지를 눌러 현재 상태로 Plan A와 Plan B를 다시 계산해요.</p>` +
    state.favorites.map((p, i) => `<div class="fav-row"><button class="ex" data-q="${esc(p.name)} 근처 충전소와 Plan B 알려줘"><i>📍</i><span>${esc(p.name)}<small>현재 조건으로 다시 추천</small></span></button><button class="fav-remove" data-remove-fav="${i}" aria-label="저장 삭제">×</button></div>`).join("");
}
function renderView() {
  $$("#nav button").forEach((b) => b.classList.toggle("on", b.dataset.view === state.view));
  const el = $("#result");
  if (state.view === "map") { el.innerHTML = mapPanel(); overview(); }
  else if (state.view === "trips") el.innerHTML = tripsPanel();
  else if (state.view === "places") el.innerHTML = placesPanel();
  else el.innerHTML = state.current ? resultHtml(state.current) : welcome();
  el.scrollTop = 0;
}

/* ---------------- Plan A 상태 변화 감시 ---------------- */
function hideSwitchToast() { $("#switchToast").hidden = true; }
function showSwitchToast(live) {
  const r = state.current;
  if (!r || !r.ok || !r.B) return;
  $("#toastText").textContent = `${r.A.name}이(가) ‘${live.text}’ 상태로 바뀌었습니다. ${r.B.name}(으)로 경로를 전환할 수 있어요.`;
  $("#toastGo").href = r.B.directions;
  $("#switchToast").hidden = false;
}
async function monitorCurrentA() {
  const r = state.current;
  if (!r || !r.ok || !r.A || !r.A.id || !state.meta || state.meta.status.live.state !== "on") return;
  try {
    const checked = await fetch(`/api/live/station/${encodeURIComponent(r.A.id)}`).then((x) => x.json());
    if (!checked.ok || !checked.live) return;
    const backup = await fetch("/api/planb/recheck", {method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({facility_id: r.A.id, exclude_ids: r.backup_excluded_ids || []})}).then((x) => x.json());
    if (state.current !== r) return;
    const backupChanged = backup.ok && (r.B?.id !== backup.B?.id || r.B?.live?.tone !== backup.B?.live?.tone || r.plan_b_search?.state !== backup.plan_b_search?.state);
    if (backup.ok) {
      if (r.B?.id === backup.B?.id && r.B?.reach && backup.B) backup.B.reach = r.B.reach;
      r.B = backup.B; r.plan_b_search = backup.plan_b_search;
      if (backupChanged) {
        r.summary = `Plan A는 ${r.A.name}입니다. ` + (r.B ? `현재 확인된 Plan B는 ${r.B.name}입니다. ` : "") + backup.plan_b_search.message;
        r.highlight = [r.A.name, ...(r.B ? [r.B.name] : [])];
        r.notes = r.notes.filter((n) => !/Plan B|대체 후보|같은 건물|독립 대안|대체시설/.test(n.text));
        r.notes.push({tone: r.B ? "info" : "warn", text: backup.plan_b_search.message});
        hideSwitchToast();
        if(state.view==="recommend") drawResult(r);
      }
    }
    const prevText = r.A.live?.text; const previous = state.liveATone;
    state.liveATone = checked.live.tone;
    r.A.live = checked.live;
    if (checked.live.tone === "good" || !r.B) hideSwitchToast();
    if (previous === "good" && (checked.live.tone === "warn" || checked.live.tone === "bad")) showSwitchToast(checked.live);
    if (state.view === "recommend" && (prevText !== checked.live.text || previous !== checked.live.tone || backupChanged)) renderView();
  } catch (e) { /* 다음 주기에 다시 확인 */ }
}

/* ---------------- 질문 실행 ---------------- */
let askSequence=0;
function sizeComposer(){
  const box=$("#askInput");box.style.height="auto";
  box.style.height=Math.min(152,Math.max(36,box.scrollHeight))+"px";
  box.style.overflowY=box.scrollHeight>152?"auto":"hidden";
}
function wireComposer(composer,form,send){
  composer.addEventListener("input",()=>{composer.setCustomValidity("");sizeComposer();});
  window.addEventListener("resize",sizeComposer);
  composer.addEventListener("keydown",e=>{if(e.key==="Enter"&&!e.shiftKey&&!e.isComposing&&e.keyCode!==229){e.preventDefault();form.requestSubmit();}});
  form.addEventListener("submit",e=>{
    e.preventDefault();const query=composer.value;
    if(!query.trim()||Array.from(query).length>2000){composer.setCustomValidity(query.trim()?"질문을 2,000자 이내로 작성해 주세요.":"질문을 입력해 주세요.");composer.reportValidity();return;}
    composer.value="";sizeComposer();send(query);
  });
}
async function ask(query) {
  query = (query || "").trim();
  if (!query) { $("#askInput").focus(); return; }
  state.view = "recommend";
  $$("#nav button").forEach((b) => b.classList.toggle("on", b.dataset.view === "recommend"));
  const seq=++askSequence, token=window.crypto?.randomUUID?.(), steps=["질문 이해","장소 찾기","주변 충전소 비교","실시간 상태 확인","Plan B 계산","답변 작성"];
  $("#result").innerHTML = head("AI가 확인하고 있어요") + `<div class="loading" role="status"><p>“${esc(query)}”</p>
    <div class="skel" style="width:92%"></div><div class="skel" style="width:70%"></div><div class="skel" style="width:84%"></div><ol>${steps.map((s,i)=>`<li class="${i?"":"on"}">${s}</li>`).join("")}</ol></div>`;
  let polling=false;const timer=token&&setInterval(async()=>{if(polling||seq!==askSequence)return;polling=true;try{const d=await fetch("/api/progress/"+token,{cache:"no-store"}).then(r=>r.json());if(d.step&&seq===askSequence)$$("#result .loading li").forEach((el,i)=>el.classList.toggle("on",i+1===d.step));}catch{}finally{polling=false;}},550);
  if (window.innerWidth < 1080) $(".content").scrollIntoView({ behavior: "smooth" });
  try {
    const s = state.s;
    const historyReady = loadChargeHistory();
    const res = await fetch("/api/ask", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, progress_id:token, connector: state.s.connector || null, vehicle: vehicle().name, battery: s.battery, battery_override: state.batteryDirty, origin: s.origin, origin_lat: s.origin_lat, origin_lon: s.origin_lon, preference: s.preference, thread_id: state.threadId }) })
      .then((r) => {if(!r.ok)throw Error("요청 실패");return r.json();});
    if (res.ok) await historyReady;
    if(seq!==askSequence)return;
    if(res.preference) state.s.preference=res.preference;
    state.current = res; state.liveATone = res.ok && res.A.live ? res.A.live.tone : null;
    if (res.battery != null && Number.isFinite(+res.battery)) { state.s.battery = +res.battery; state.batteryDirty = false; renderCar(); saveSettings(); }
    const recentPlan = res.ok
      ? { ok: true, dest: { name: res.dest.name }, A: { name: res.A.name }, B: res.B ? { name: res.B.name } : null }
      : { ok: false };
    state.history.push({ query, result: recentPlan }); state.history=state.history.slice(-10); saveHistory(); hideSwitchToast();
    renderView();
    if (res.ok) drawResult(res); else overview();
    fetch("/api/status").then((r) => r.json()).then(renderStatus);
  } catch (e) {
    if(seq!==askSequence)return;
    $("#result").innerHTML = head("요청을 마치지 못했어요") + `<div class="empty">서버 연결을 확인한 뒤 다시 시도해 주세요.</div><p class="failed-question">${esc(query)}</p><button class="subbtn" data-q="${esc(query)}">같은 질문으로 다시 시도</button>`;
  }finally{clearInterval(timer);}
}

/* ---------------- 시작 ---------------- */
function flowers() {
  const g = $("#flowers"); let html = "";
  for (let k = 0; k < 140; k++) {
    const x = 930 + Math.random() * 280, y = 200 + Math.random() * 70 - (x - 930) * 0.12;
    html += `<circle cx="${x.toFixed(0)}" cy="${y.toFixed(0)}" r="${(3 + Math.random() * 4).toFixed(1)}"/>`;
  }
  g.innerHTML = html + `<path d="M900 260 Q1050 200 1200 180 V260Z" fill="#4E8A3A" opacity=".55"/>`;
}
async function init() {
  flowers(); decorateSettings(); initMap(); loadSettings(); setLegend("overview");
  $("#connectorSel").addEventListener("change", () => {state.s.connector = $("#connectorSel").value; saveSettings(); renderCar();});
  state.meta = await fetch("/api/meta").then((r) => r.json());
  if (window.innerWidth <= 640) $("#settingsBox").removeAttribute("open");
  if (!state.s.vehicle) state.s.vehicle = state.meta.vehicles[0].name;
  $("#vehicleSel").innerHTML = state.meta.vehicles.map((v) => `<option>${esc(v.name)}</option>`).join("");
  renderCar(); renderStatus(state.meta.status); renderView(); loadPoints();
  KakaoView.start(state.meta.map_js_key);

  wireComposer($("#askInput"),$("#askForm"),ask);
  $("#nav").addEventListener("click", (e) => {
    const b = e.target.closest("button"); if (!b) return;
    state.view = b.dataset.view; renderView();
    if (state.view === "recommend" && state.current && state.current.ok) drawResult(state.current);
    else if (state.view !== "map" && !state.current) overview();
  });
  $("#result").addEventListener("click", (e) => {
    const q = e.target.closest("[data-q]"); if (q) return ask(q.dataset.q);
    const h = e.target.closest("[data-h]");
    if (h) { const item = state.history[+h.dataset.h]; newConversation().then(() => ask(item.result?.dest?.name || item.query)); return; }
    const rm = e.target.closest("[data-remove-fav]");
    if (rm) { state.favorites.splice(+rm.dataset.removeFav, 1); saveFavorites(); renderView(); return; }
    if (e.target.closest("[data-save]") && state.current?.ok) {
      const name = state.current.dest.name;
      if (!state.favorites.some((f) => f.name === name)) state.favorites.unshift({name}); state.favorites=state.favorites.slice(0,12);
      saveFavorites(); renderView(); return;
    }
    if (e.target.closest("[data-reset]")) { newConversation().then(() => { renderView(); overview(); $("#askInput").value = ""; $("#askInput").focus(); }); }
  });
  $("#result").addEventListener("submit", (e) => {
    if (!e.target.matches(".place-retry")) return;
    e.preventDefault(); const name = $("#retryName").value.trim(); if (name) ask(name);
  });
  $("#vehicleSel").addEventListener("change", (e) => { state.s.vehicle = e.target.value; saveSettings(); renderCar(); });
  $("#battRange").addEventListener("input", (e) => { state.s.battery = +e.target.value; state.batteryDirty = true; renderCar(); });
  $("#battRange").addEventListener("change", saveSettings);
  $("#prefTiles").addEventListener("click", (e) => { const b = e.target.closest("button"); if (!b) return; state.s.preference = b.dataset.v; saveSettings(); renderCar(); if(state.current?.ok) ask(state.current.dest.name); });
  $("#originInput").addEventListener("change", (e) => {
    const v = e.target.value.trim(); if (v === "내 위치") return;
    state.s.origin = v; state.s.origin_lat = null; state.s.origin_lon = null; $("#geoHint").textContent = ""; saveSettings();
  });
  $("#geoBtn").addEventListener("click", () => {
    if (!navigator.geolocation) { $("#geoHint").textContent = "이 브라우저는 위치 기능을 지원하지 않아요."; return; }
    $("#geoHint").textContent = "위치를 확인하고 있어요...";
    navigator.geolocation.getCurrentPosition((p) => {
      state.s.origin_lat = p.coords.latitude; state.s.origin_lon = p.coords.longitude; state.s.origin = "";
      renderCar(); $("#geoHint").textContent = "현재 위치를 출발지로 쓸게요.";
    }, () => { $("#geoHint").textContent = "위치를 가져오지 못했어요. 장소 이름을 적어 주세요."; }, { timeout: 8000 });
  });
  const open = () => { $("#sheetBg").hidden = false; $("#connSheet").hidden = false; $("#checkMsg").textContent = ""; };
  const close = () => { $("#sheetBg").hidden = true; $("#connSheet").hidden = true; };
  $("#connBtn").addEventListener("click", open); $("#sheetBg").addEventListener("click", close);
  $("#toastClose").addEventListener("click", hideSwitchToast);
  $$("[data-close]").forEach((b) => b.addEventListener("click", close));
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") close(); });
  $("#liveRefresh").addEventListener("click", async () => {
    $("#checkMsg").textContent = "실시간 상태를 다시 불러오고 있어요...";
    const st = await fetch("/api/live/refresh", { method: "POST" }).then((r) => r.json());
    renderStatus(st); state.meta.status = st; await loadPoints(); await monitorCurrentA();
    $("#checkMsg").textContent = `실시간: ${st.live.text}`;
  });
  $("#datahubRefresh").addEventListener("click", async () => {
    $("#checkMsg").textContent = "제주데이터허브 연결을 확인하고 있어요…";
    const st = await fetch("/api/datahub/refresh", { method: "POST" }).then((r) => r.json());
    renderStatus(st); state.meta.status = st;
    $("#checkMsg").textContent = hubStatusSummary(st.datahub);
  });
  $("#geminiCheck").addEventListener("click", async () => {
    $("#checkMsg").textContent = "Gemini에 짧게 물어보고 있어요...";
    const r = await fetch("/api/gemini/check", { method: "POST" }).then((x) => x.json());
    $("#checkMsg").textContent = (r.ok ? "✅ " : "⚠️ ") + r.message;
    fetch("/api/status").then((x) => x.json()).then(renderStatus);
  });
  setInterval(monitorCurrentA, 60000);
}
init();
