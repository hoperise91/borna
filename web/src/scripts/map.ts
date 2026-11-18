// The map page: MapLibre + PMTiles, a sidebar to search and browse by county, and a road panel.
import * as maplibregl from "maplibre-gl";
import type { ExpressionSpecification, GeoJSONSource, LngLatLike } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import { Protocol } from "pmtiles";
import { countiesSorted, countyName } from "../lib/counties";
import type { Strings } from "../lib/i18n";
import {
  CATEGORY_COLOR, CATEGORY_ORDER, DATA_URL, QUALITY_COLOR, SURFACE_COLOR, type IndexRow,
  type LonLat, type Quality, type Road, fetchIndex, fetchRoad, fold, formatKm, formatLength,
  locate, measure, parseQuery, qualityShares,
} from "../lib/roads";
import { liveStrip } from "../lib/strip";

const BASEMAP = "https://tiles.openfreemap.org/styles/positron";
const RO_BOUNDS: [[number, number], [number, number]] = [[20.2, 43.6], [29.75, 48.3]];
type Mode = "category" | "surface" | "maxspeed" | "aadt" | "quality";

const esc = (v: unknown) => String(v ?? "").replace(/[&<>"]/g, (c) => `&#${c.charCodeAt(0)};`);
const shield = (ref: string, cat: string, lg = false) =>
  `<span class="shield${lg ? " lg" : ""}" data-cat="${esc(cat)}">${esc(ref)}</span>`;

export function initMap(root: HTMLElement) {
  const s: Strings = JSON.parse(root.dataset.strings!);
  const lang = root.dataset.lang!;
  const roadUrl = root.dataset.roadUrl!;
  const view = root.querySelector<HTMLElement>("#view")!;
  const homeHTML = view.innerHTML;
  const input = root.querySelector<HTMLInputElement>("#q")!;
  const clearBtn = root.querySelector<HTMLButtonElement>("#q-clear")!;
  const legend = root.querySelector<HTMLElement>("#legend")!;
  const cat = (c: string) => (s as Record<string, string>)[`cat_${c}`] ?? c;
  const qual = (q: string) => (s as Record<string, string>)[`q_${q}`] ?? q;

  let index: IndexRow[] = [];
  let mode: Mode = "category";
  let selected: string | null = null;
  let stopStrip: (() => void) | null = null;
  const stack: (() => void)[] = []; // sidebar history for "Back"
  let current: () => void = renderHome;

  // ---- map --------------------------------------------------------------------------
  maplibregl.setWorkerUrl(workerUrl); // bundled by Vite (an ES-module worker)
  const protocol = new Protocol();
  maplibregl.addProtocol("pmtiles", protocol.tile);
  const map = new maplibregl.Map({
    container: root.querySelector<HTMLElement>("#map")!,
    style: BASEMAP,
    bounds: RO_BOUNDS,
    fitBoundsOptions: { padding: 24 },
    attributionControl: {
      compact: true,
      customAttribution: "© OpenStreetMap contributors (ODbL) · HG 540/2000 · INS · data.gov.ro · Bornă",
    },
  });
  map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
  map.addControl(new maplibregl.GeolocateControl({ trackUserLocation: false }), "top-right");
  map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-right");

  const pin = new maplibregl.Marker({ element: Object.assign(document.createElement("div"), { className: "km-pin" }) });
  const pinPopup = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 16 });
  const hoverPopup = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 12, className: "hover-pop" });

  // Line width by category and zoom, times k plus `add` px (zoom must stay the top-level input).
  const width = (k = 1, add = 0): ExpressionSpecification => [
    "interpolate", ["exponential", 1.6], ["zoom"],
    5, ["+", add, ["*", k, ["match", ["get", "t"], ["A", "DX"], 2.2, "DN", 1.6, "V", 1.1, "DJ", 0.8, 0.6]]],
    10, ["+", add, ["*", k, ["match", ["get", "t"], ["A", "DX"], 4, "DN", 3.2, "V", 2.6, "DJ", 2.2, 1.4]]],
    14, ["+", add, ["*", k, ["match", ["get", "t"], ["A", "DX"], 8, "DN", 6.5, "V", 5, "DJ", 4.5, 3]]],
  ];
  const catColor: ExpressionSpecification = [
    "match", ["get", "t"], ...Object.entries(CATEGORY_COLOR).flat(), "#7c7c7c",
  ] as unknown as ExpressionSpecification;
  const qualityColor: ExpressionSpecification = [
    "match", ["get", "q"], ...Object.entries(QUALITY_COLOR).flat(), "#999",
  ] as unknown as ExpressionSpecification;

  map.on("load", () => {
    const before = map.getStyle().layers.find((l) => l.type === "symbol")?.id;
    map.addSource("borna", {
      type: "vector",
      url: `pmtiles://${new URL(`${DATA_URL}/borna.pmtiles`, location.href).href}`,
    });
    map.addSource("sel", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
    const line = { "line-join": "round", "line-cap": "round" } as const;

    map.addLayer({ id: "roads-casing", type: "line", source: "borna", "source-layer": "roads", layout: line,
      paint: { "line-color": "#ffffff", "line-width": width(1, 2), "line-opacity": 0.85 } }, before);
    map.addLayer({ id: "road-hover", type: "line", source: "borna", "source-layer": "roads", layout: line,
      filter: ["==", ["get", "k"], ""],
      paint: { "line-color": "#1d1c1a", "line-opacity": 0.28, "line-width": width(1, 7) } }, before);
    map.addLayer({ id: "sel-halo", type: "line", source: "sel", layout: line,
      paint: { "line-color": "#ffcf33", "line-width": ["interpolate", ["linear"], ["zoom"], 5, 9, 14, 18],
        "line-opacity": 0.9, "line-blur": 1 } }, before);
    map.addLayer({ id: "roads", type: "line", source: "borna", "source-layer": "roads", layout: line,
      paint: { "line-color": catColor, "line-width": width() } }, before);
    map.addLayer({ id: "surface", type: "line", source: "borna", "source-layer": "surface", layout: { ...line, visibility: "none" },
      paint: { "line-width": width(1.15), "line-color": [
        "match", ["get", "v"], ...Object.entries(SURFACE_COLOR).flat(), "#a3a3a3"] as unknown as ExpressionSpecification } }, before);
    map.addLayer({ id: "maxspeed", type: "line", source: "borna", "source-layer": "maxspeed", layout: { ...line, visibility: "none" },
      paint: { "line-width": width(1.15), "line-color": [
        "case", [">", ["to-number", ["get", "v"], 0], 0],
        ["step", ["to-number", ["get", "v"], 0], "#b2182b", 31, "#ef8a62", 51, "#f4c95d", 71, "#7fbf7b", 91, "#2c9c5a", 111, "#00563b"],
        "#a3a3a3"] } }, before);
    map.addLayer({ id: "aadt", type: "line", source: "borna", "source-layer": "aadt", layout: { ...line, visibility: "none" },
      paint: {
        "line-color": ["step", ["get", "v"], "#cbc9e2", 10000, "#9e9ac8", 20000, "#6a51a3", 40000, "#3f007d"],
        "line-width": ["interpolate", ["linear"], ["zoom"],
          5, ["interpolate", ["linear"], ["get", "v"], 3000, 1.5, 20000, 3.5, 75000, 8],
          12, ["interpolate", ["linear"], ["get", "v"], 3000, 4, 20000, 8, 75000, 16]],
      } }, before);
    map.addLayer({ id: "sel-line", type: "line", source: "sel", layout: line,
      paint: { "line-color": ["get", "color"], "line-width": ["interpolate", ["linear"], ["zoom"], 5, 3, 14, 8] } }, before);

    // hover
    map.on("mousemove", "roads", (e) => {
      const f = e.features?.[0];
      if (!f) return;
      map.getCanvas().style.cursor = "pointer";
      const k = f.properties.k as string;
      map.setFilter("road-hover", ["==", ["get", "k"], k]);
      hoverPopup.setLngLat(e.lngLat)
        .setHTML(`${shield(f.properties.r, f.properties.t)}${f.properties.k.includes("-")
          ? ` <span class="small muted">${esc(countyName(k.split("-")[0]))}</span>` : ""}`)
        .addTo(map);
    });
    map.on("mouseleave", "roads", () => {
      map.getCanvas().style.cursor = "";
      map.setFilter("road-hover", ["==", ["get", "k"], ""]);
      hoverPopup.remove();
    });
    // click: the most important road under the pointer
    map.on("click", (e) => {
      const box: [maplibregl.PointLike, maplibregl.PointLike] = [[e.point.x - 6, e.point.y - 6], [e.point.x + 6, e.point.y + 6]];
      const feats = map.queryRenderedFeatures(box, { layers: ["roads"] });
      if (!feats.length) return;
      feats.sort((a, b) => CATEGORY_ORDER.indexOf(a.properties.t) - CATEGORY_ORDER.indexOf(b.properties.t));
      hoverPopup.remove();
      selectRoad(feats[0].properties.k as string, { at: [e.lngLat.lng, e.lngLat.lat], push: true });
    });

    root.querySelector(".maplibregl-ctrl-attrib")?.classList.remove("maplibregl-compact-show");
    applyMode();
    restoreFromUrl();
  });

  // ---- layer modes & legend -----------------------------------------------------------
  root.querySelectorAll<HTMLButtonElement>(".layer-switch button").forEach((b) =>
    b.addEventListener("click", () => {
      mode = b.dataset.layer as Mode;
      root.querySelectorAll(".layer-switch button").forEach((x) => x.setAttribute("aria-checked", String(x === b)));
      applyMode();
    }));

  function applyMode() {
    if (!map.getLayer("roads")) return;
    const neutral = "#cdc6b8";
    map.setPaintProperty("roads", "line-color", mode === "category" ? catColor : mode === "quality" ? qualityColor : neutral);
    for (const id of ["surface", "maxspeed", "aadt"]) map.setLayoutProperty(id, "visibility", id === mode ? "visible" : "none");
    const row = (color: string, label: string, h = 5) =>
      `<div class="row"><span class="sw" style="background:${color};height:${h}px"></span>${esc(label)}</div>`;
    let html = "";
    if (mode === "category") html = ["A", "DN", "V", "DJ", "DC", "DP"].map((c) => row(CATEGORY_COLOR[c], cat(c))).join("");
    if (mode === "surface") html = Object.entries(SURFACE_COLOR).map(([k, c]) => row(c, (s as Record<string, string>)[`s_${k}`])).join("");
    if (mode === "maxspeed") html = [["#b2182b", "≤ 30"], ["#ef8a62", "50"], ["#f4c95d", "70"], ["#7fbf7b", "90"], ["#2c9c5a", "100–110"], ["#00563b", "130"]]
      .map(([c, l]) => row(c, `${l} km/h`)).join("");
    if (mode === "aadt") html = [["#cbc9e2", "< 10 000"], ["#9e9ac8", "10–20 000"], ["#6a51a3", "20–40 000"], ["#3f007d", "> 40 000"]]
      .map(([c, l], i) => row(c, l, 3 + i * 2)).join("") + `<div class="small muted" style="max-width:190px;margin-top:4px">${esc(s.aadt_note)}</div>`;
    if (mode === "quality") html = (["calibrated", "interpolated", "estimated"] as Quality[])
      .map((q) => row(QUALITY_COLOR[q], `${qual(q)}: ${(s as Record<string, string>)[`q_${q}_long`]}`)).join("");
    legend.innerHTML = html;
  }

  // ---- sidebar views --------------------------------------------------------------------
  function show(render: () => void, push: boolean) {
    if (push) stack.push(current);
    current = render;
    stopStrip?.();
    stopStrip = null;
    render();
    view.scrollTop = 0;
  }
  function back() {
    show(stack.pop() ?? renderHome, false);
  }
  const backBtn = () => `<button type="button" class="back" data-back>← ${esc(s.back)}</button>`;
  view.addEventListener("click", (e) => {
    const t = e.target as HTMLElement;
    if (t.closest("[data-back]")) return back();
    const ex = t.closest<HTMLElement>("[data-example]");
    if (ex) { input.value = ex.dataset.example!; onSearch(true); return; }
    const county = t.closest<HTMLElement>("[data-county]");
    if (county) return show(() => renderCounty(county.dataset.county!, "all"), true);
    const road = t.closest<HTMLElement>("[data-road]");
    if (road) {
      const km = road.dataset.km ? Number(road.dataset.km) : undefined;
      return selectRoad(road.dataset.road!, { fit: km == null, km, push: true });
    }
  });

  function renderHome() {
    view.innerHTML = homeHTML;
    const counts = new Map<string, number>();
    for (const r of index) {
      if (r[2]) counts.set(r[2], (counts.get(r[2]) ?? 0) + 1);
      for (const c of r[7]) counts.set(c, (counts.get(c) ?? 0) + 1);
    }
    view.querySelector("#county-list")!.innerHTML = countiesSorted().map(([code, name]) =>
      `<li><button type="button" data-county="${code}"><span>${esc(name)}</span><span class="n">${counts.get(code) ?? ""}</span></button></li>`).join("");
  }

  const roadItem = (r: IndexRow, km?: number) => {
    const missing = r[6] === "no_geometry";
    const where = r[2] ? countyName(r[2]) : s.national_road;
    return `<li><button type="button" class="road-item${missing ? " missing" : ""}" data-road="${esc(r[0])}"${km != null ? ` data-km="${km}"` : ""}>
      ${shield(r[1], r[3])}<span class="route">${esc(r[4] || cat(r[3]))}</span>
      <span class="meta">${esc(where)}${missing ? ` · ${esc(s.not_on_map)}` : ""}</span></button></li>`;
  };

  function renderCounty(code: string, filter: string) {
    const rows = index.filter((r) => r[2] === code || r[7].includes(code));
    const cats = CATEGORY_ORDER.filter((c) => rows.some((r) => r[3] === c));
    const shown = filter === "all" ? rows : rows.filter((r) => r[3] === filter);
    view.innerHTML = `<section>${backBtn()}
      <h2 class="side-h" style="font-size:24px">${esc(countyName(code))}</h2>
      <div class="filters">
        <button type="button" class="chip" data-filter="all" aria-pressed="${filter === "all"}">${esc(s.all)} · ${rows.length}</button>
        ${cats.map((c) => `<button type="button" class="chip" data-filter="${c}" aria-pressed="${filter === c}">${c} · ${rows.filter((r) => r[3] === c).length}</button>`).join("")}
      </div>
      <ul class="road-list">${shown.map((r) => roadItem(r)).join("")}</ul></section>`;
    view.querySelectorAll<HTMLButtonElement>("[data-filter]").forEach((b) =>
      b.addEventListener("click", () => { current = () => renderCounty(code, b.dataset.filter!); current(); }));
    const own = rows.filter((r) => r[2] === code && r[5]);
    const b = (own.length ? own : rows).map((r) => r[5]).filter(Boolean) as [number, number, number, number][];
    if (b.length) map.fitBounds([[Math.min(...b.map((x) => x[0])), Math.min(...b.map((x) => x[1]))],
      [Math.max(...b.map((x) => x[2])), Math.max(...b.map((x) => x[3]))]], { padding: 40, duration: 700 });
  }

  // ---- search ---------------------------------------------------------------------------
  let t: number | undefined;
  input.addEventListener("input", () => {
    clearBtn.hidden = !input.value;
    window.clearTimeout(t);
    t = window.setTimeout(() => onSearch(false), 140);
  });
  root.querySelector("#search-form")!.addEventListener("submit", (e) => { e.preventDefault(); onSearch(true); });
  clearBtn.addEventListener("click", () => { input.value = ""; clearBtn.hidden = true; stack.length = 0; show(renderHome, false); input.focus(); });

  function onSearch(enter: boolean) {
    const q = input.value.trim();
    if (!q) { stack.length = 0; show(renderHome, false); return; }
    const p = parseQuery(q);
    let rows: IndexRow[] = [];
    if (p.ref) {
      rows = index.filter((r) => r[1] === p.ref);
      if (!rows.length) rows = index.filter((r) => r[1].startsWith(p.ref!)).slice(0, 60);
      if (enter && rows.length === 1 && rows[0][1] === p.ref) {
        return selectRoad(rows[0][0], { km: p.km ?? undefined, fit: p.km == null, push: true });
      }
    }
    const fq = fold(q).replace(/\s+/g, " ");
    const counties = p.ref ? [] : countiesSorted().filter(([, n]) => fold(n).includes(fq));
    if (!p.ref) {
      const compact = fq.replace(/\s/g, "");
      rows = index.filter((r) => r[1].startsWith(compact) || fold(r[4]).includes(fq)).slice(0, 60);
    }
    const km = p.km ?? undefined;
    const render = () => {
      view.innerHTML = `<section>
        ${counties.map(([c, n]) => `<button type="button" class="road-item" data-county="${c}"><span class="shield" style="background:var(--ink)">${c}</span><span class="route"><b>${esc(n)}</b> · ${esc(s.browse_counties)}</span></button>`).join("")}
        ${rows.length ? `<ul class="road-list">${rows.map((r) => roadItem(r, km)).join("")}</ul>`
          : counties.length ? "" : `<p class="msg">${esc(s.no_results)}</p>`}
      </section>`;
    };
    if (current === render) render(); else { stack.length = 0; show(render, false); }
  }

  // ---- road selection -------------------------------------------------------------------
  async function selectRoad(key: string, opts: { at?: LonLat; km?: number; fit?: boolean; push?: boolean } = {}) {
    let road: Road;
    try { road = await fetchRoad(key); } catch { view.innerHTML = `<p class="msg">${esc(s.road_not_found)}</p>`; return; }
    selected = key;
    const color = CATEGORY_COLOR[road.category] ?? "#7c7c7c";
    (map.getSource("sel") as GeoJSONSource | undefined)?.setData({
      type: "FeatureCollection",
      features: road.segments.map(([, , , coords]) => ({
        type: "Feature", properties: { color }, geometry: { type: "LineString", coordinates: coords },
      })),
    });

    let here: { km: number; quality: Quality } | null = null;
    let outOfRange = false;
    if (opts.at) {
      const m = measure(road, opts.at);
      if (m) { here = m; placePin(m.point, road, m.km); }
    } else if (opts.km != null) {
      const loc = locate(road, opts.km);
      if (loc) {
        here = { km: opts.km, quality: loc.quality };
        placePin(loc.point, road, opts.km);
        map.flyTo({ center: loc.point as LngLatLike, zoom: Math.max(map.getZoom(), 14), duration: 900 });
      } else { outOfRange = true; pin.remove(); pinPopup.remove(); }
    } else { pin.remove(); pinPopup.remove(); }
    if (opts.fit && road.bbox) {
      map.fitBounds([[road.bbox[0], road.bbox[1]], [road.bbox[2], road.bbox[3]]], { padding: 50, maxZoom: 14, duration: 800 });
    }
    const url = new URL(location.href);
    url.searchParams.set("r", key);
    if (here) url.searchParams.set("km", here.km.toFixed(3)); else url.searchParams.delete("km");
    url.searchParams.delete("q");
    history.replaceState(null, "", url);
    show(() => renderRoad(road, here, outOfRange), opts.push ?? false);
  }

  function placePin(p: LonLat, road: Road, km: number) {
    pin.setLngLat(p as LngLatLike).addTo(map);
    pinPopup.setLngLat(p as LngLatLike).setOffset(16)
      .setHTML(`${shield(road.ref, road.category)} <span class="km">km ${formatKm(km)}</span>`).addTo(map);
  }

  function renderRoad(road: Road, here: { km: number; quality: Quality } | null, outOfRange: boolean) {
    const onMap = road.segments.length > 0;
    const shares = qualityShares(road);
    const aadt = (road.attributes.aadt ?? []).map((e) => Number(e[2]));
    const statusText = (s as Record<string, string>)[`status_${road.lrs.status ?? "no_geometry"}`] ?? "";
    const through = road.counties ? [...new Set(road.counties.map((c) => c[0]))] : [];
    const srcIds = new Set(Object.values(road.attributes).flat().map((e) => e[3]));
    const sources = [road.legal_source?.split(" (")[0] ?? "HG 540/2000",
      onMap ? "© OpenStreetMap (ODbL)" : "", srcIds.has("aadt_end") ? "MMAP, data.gov.ro (CC BY 4.0)" : ""].filter(Boolean);

    view.innerHTML = `<section>${backBtn()}
      <div class="detail-head">${shield(road.ref, road.category, true)}
        <div><h2>${esc(cat(road.category))}</h2>
        <div class="small muted">${esc(road.county ? countyName(road.county) : s.national_road)}</div></div></div>
      <p class="detail-route">${esc(road.route ?? "")}</p>
      ${here ? `<div class="here"><span class="small muted">${esc(s.here)}</span>
        <span class="km">km ${formatKm(here.km)}</span>
        <span class="q" data-q="${here.quality}" title="${esc((s as Record<string, string>)[`q_${here.quality}_long`])}">${esc(qual(here.quality))}</span></div>` : ""}
      ${outOfRange ? `<p class="msg">${esc(s.km_out_of_range)}</p>` : ""}
      <dl class="facts">
        <dt>${esc(s.official_length)}</dt><dd>${formatLength(road.length_official, lang)}</dd>
        <dt>${esc(s.official_km)}</dt><dd class="mono">${formatKm(road.km_from)} – ${formatKm(road.km_to)}</dd>
        <dt>${esc(s.on_map)}</dt><dd>${onMap ? `${formatLength(road.lrs.path_km, lang)} · <span class="muted">${esc(statusText)}</span>` : esc(s.not_on_map)}</dd>
        ${onMap ? `<dt>${esc(s.km_quality)}</dt><dd>${Math.round(shares.calibrated * 100)}% ${esc(qual("calibrated"))}
          <div class="qbar">${(["calibrated", "interpolated", "estimated"] as Quality[]).map((q) =>
            `<span style="width:${shares[q] * 100}%;background:${QUALITY_COLOR[q]}"></span>`).join("")}</div></dd>` : ""}
        ${through.length ? `<dt>${esc(s.through)}</dt><dd>${through.map((c) => esc(countyName(c))).join(", ")}</dd>` : ""}
        ${aadt.length ? `<dt>${esc(s.aadt)}</dt><dd>${Math.min(...aadt).toLocaleString()} – ${Math.max(...aadt).toLocaleString()} ${esc(s.vehicles_day)}</dd>` : ""}
      </dl>
      ${onMap ? `<form class="goto" id="goto"><input inputmode="decimal" placeholder="${esc(s.go_to_km)}, ${formatKm(((road.km_from ?? 0) + (road.km_to ?? 0)) / 2)}" aria-label="${esc(s.go_to_km)}"/>
        <button class="btn">${esc(s.go)}</button></form>
        <div class="mini-strip" id="mini-strip"></div>
        <div class="mini-legend"><span>${esc(s.surface)}</span><span>·</span><span>${esc(s.lanes)}</span><span>·</span><span>${esc(s.maxspeed)}</span></div>` : ""}
      <div class="actions">
        <a class="btn primary" href="${roadUrl}?r=${encodeURIComponent(road.key)}">${esc(s.road_page)} →</a>
        ${onMap ? `<button type="button" class="btn" id="fit">${esc(s.zoom_to_road)}</button>` : ""}
      </div>
      <p class="src">${esc(s.sources)}: ${sources.map(esc).join(" · ")}</p></section>`;

    if (onMap) {
      stopStrip = liveStrip(view.querySelector<HTMLElement>("#mini-strip")!, road, s, { compact: true });
      view.querySelector("#fit")!.addEventListener("click", () => road.bbox && map.fitBounds(
        [[road.bbox[0], road.bbox[1]], [road.bbox[2], road.bbox[3]]], { padding: 50, maxZoom: 14 }));
      view.querySelector("#goto")!.addEventListener("submit", (e) => {
        e.preventDefault();
        const v = (e.currentTarget as HTMLFormElement).querySelector("input")!.value;
        const p = parseQuery(`${road.ref} ${v}`);
        if (p.km != null) selectRoad(road.key, { km: p.km });
      });
    }
  }

  function clearSelection() {
    selected = null;
    (map.getSource("sel") as GeoJSONSource | undefined)?.setData({ type: "FeatureCollection", features: [] });
    pin.remove(); pinPopup.remove();
    const url = new URL(location.href);
    url.searchParams.delete("r"); url.searchParams.delete("km");
    history.replaceState(null, "", url);
  }
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && selected) { clearSelection(); back(); }
  });

  function restoreFromUrl() {
    const p = new URLSearchParams(location.search);
    const r = p.get("r");
    const km = p.get("km");
    if (r) selectRoad(r, { km: km != null ? Number(km) : undefined, fit: km == null });
    else if (p.get("q")) { input.value = p.get("q")!; clearBtn.hidden = false; onSearch(true); }
  }

  // ---- start ------------------------------------------------------------------------------
  fetchIndex().then((rows) => {
    index = rows;
    if (current === renderHome) renderHome();
  });
  renderHome();
}
