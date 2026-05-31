/**
 * map_renderer.js — PreCrash SoS
 *
 * Feature 1: Real OpenStreetMap via Leaflet.js, centred on Bengaluru.
 *            Black-spot zones shown as pulsing red circles.
 *            Live responders shown as green markers, updated every 5s.
 *
 * Feature 2: Auto Risk Scheduler — every 30s scores a random black-spot
 *            zone via the ML engine and auto-fires a critical incident
 *            alert if the risk score ≥ 0.75.
 */

const BACKEND_URL   = "http://localhost:5050";
const ML_ENGINE_URL = "http://localhost:8001";

// ─── Real Bengaluru black-spot zones ────────────────────────────────────────
const BENGALURU_ZONES = [
    { name: "Silk Board Junction",   lat: 12.9176, lon: 77.6233, hour: 8,  dow: 1, speed_limit: 60, vehicle_speed: 72, weather: 1, visibility: 7.0, traffic: 0.88, hist: 0.82, last_inc: 2.1 },
    { name: "Hebbal Flyover",        lat: 13.0358, lon: 77.5970, hour: 18, dow: 4, speed_limit: 80, vehicle_speed: 95, weather: 0, visibility: 9.0, traffic: 0.75, hist: 0.65, last_inc: 4.5 },
    { name: "Outer Ring Road",       lat: 12.9716, lon: 77.5946, hour: 22, dow: 5, speed_limit: 60, vehicle_speed: 85, weather: 1, visibility: 6.5, traffic: 0.72, hist: 0.55, last_inc: 3.2 },
    { name: "KR Puram Bridge",       lat: 13.0050, lon: 77.6960, hour: 7,  dow: 0, speed_limit: 50, vehicle_speed: 68, weather: 2, visibility: 4.5, traffic: 0.91, hist: 0.78, last_inc: 1.8 },
    { name: "Marathahalli Bridge",   lat: 12.9591, lon: 77.6974, hour: 9,  dow: 2, speed_limit: 50, vehicle_speed: 61, weather: 0, visibility: 9.5, traffic: 0.80, hist: 0.70, last_inc: 6.0 },
    { name: "Tin Factory Junction",  lat: 12.9935, lon: 77.6600, hour: 17, dow: 3, speed_limit: 50, vehicle_speed: 65, weather: 1, visibility: 7.5, traffic: 0.85, hist: 0.72, last_inc: 3.8 },
    { name: "Nagawara Junction",     lat: 13.0439, lon: 77.6205, hour: 8,  dow: 1, speed_limit: 60, vehicle_speed: 74, weather: 0, visibility: 9.0, traffic: 0.78, hist: 0.60, last_inc: 5.2 },
    { name: "Yeshwanthpur Junction", lat: 13.0213, lon: 77.5537, hour: 9,  dow: 0, speed_limit: 60, vehicle_speed: 78, weather: 1, visibility: 6.8, traffic: 0.82, hist: 0.68, last_inc: 4.1 },
];

// ─── Leaflet map instance & layer stores ────────────────────────────────────
let map = null;
const responderMarkers = {};   // unit_id → L.marker
const incidentMarkers  = [];   // temporary red alert markers

// ─────────────────────────────────────────────────────────────────────────────
//  FEATURE 1A — Initialise Leaflet map centred on Bengaluru
// ─────────────────────────────────────────────────────────────────────────────

function initMap() {
    map = L.map("leaflet-map", {
        center: [12.9716, 77.5946],   // Bengaluru city centre
        zoom: 12,
        zoomControl: true,
        attributionControl: true,
    });

    // OpenStreetMap tile layer
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 19,
    }).addTo(map);

    // Plot every known black-spot zone as a pulsing red circle
    BENGALURU_ZONES.forEach(zone => {
        const circle = L.circle([zone.lat, zone.lon], {
            color:       "#FF3B30",
            fillColor:   "#FF3B30",
            fillOpacity: 0.15,
            weight:      2,
            radius:      300,   // 300 m radius ring
        }).addTo(map);

        circle.bindTooltip(`
            <strong style="color:#FF3B30">⚠ HIGH RISK ZONE</strong><br/>
            ${zone.name}<br/>
            <span style="font-size:11px;color:#666">${zone.lat.toFixed(4)}° N, ${zone.lon.toFixed(4)}° E</span>
        `, { permanent: false, direction: "top" });
    });

    console.log("[MapRenderer] Leaflet map initialised on Bengaluru.");
}

// ─────────────────────────────────────────────────────────────────────────────
//  FEATURE 1B — Live Responder Fleet
// ─────────────────────────────────────────────────────────────────────────────

function unitIcon(id) {
    const u = id.toUpperCase();
    if (u.includes("AMBULANCE")) return "fa-truck-medical";
    if (u.includes("POLICE"))    return "fa-shield-halved";
    if (u.includes("FIRE"))      return "fa-fire-extinguisher";
    if (u.includes("QUICK"))     return "fa-motorcycle";
    return "fa-truck";
}

function buildFleetCard(responder) {
    const id     = responder.responder_user_id;
    const status = (responder.status || "ONLINE").toUpperCase();
    const sector = responder.district_id || "—";
    const lat    = responder.last_lat != null ? Number(responder.last_lat).toFixed(4) : "—";
    const lon    = responder.last_lon != null ? Number(responder.last_lon).toFixed(4) : "—";
    const icon   = unitIcon(id);
    const cls    = status === "ONLINE" ? "status-enroute" : "status-standby";
    const label  = status === "ONLINE" ? "Online"         : "Offline";

    return `
    <div class="responder-row-card ${cls}" data-unit-id="${id}">
        <div class="responder-row-header">
            <div class="responder-identity">
                <div class="identity-icon"><i class="fa-solid ${icon}"></i></div>
                <span class="responder-callsign">${id}</span>
            </div>
            <span class="responder-status-pill ${cls}">${label}</span>
        </div>
        <div class="responder-data-grid">
            <div class="data-item"><span class="data-label">Sector:</span><span class="data-val" style="color:var(--color-blue)">${sector}</span></div>
            <div class="data-item"><span class="data-label">Status:</span><span class="data-val">${status}</span></div>
            <div class="data-item"><span class="data-label">Lat:</span><span class="data-val">${lat}</span></div>
            <div class="data-item"><span class="data-label">Lon:</span><span class="data-val">${lon}</span></div>
        </div>
    </div>`;
}

/** Green circle marker for a live responder */
function makeResponderIcon() {
    return L.divIcon({
        className: "",
        html: `<div style="
            width:16px; height:16px; border-radius:50%;
            background:#06C167; border:3px solid #fff;
            box-shadow:0 0 10px rgba(6,193,103,0.7);
        "></div>`,
        iconSize: [16, 16],
        iconAnchor: [8, 8],
    });
}

/** Red pulsing marker for an active incident zone */
function makeIncidentIcon() {
    return L.divIcon({
        className: "",
        html: `<div style="
            width:20px; height:20px; border-radius:50%;
            background:#FF3B30; border:3px solid #fff;
            box-shadow:0 0 14px rgba(255,59,48,0.8);
            animation:none;
        "></div>`,
        iconSize: [20, 20],
        iconAnchor: [10, 10],
    });
}

async function refreshFleet() {
    try {
        const res  = await fetch(`${BACKEND_URL}/api/responders`);
        const data = await res.json();
        const responders = data.responders || [];

        // ── Fleet panel ─────────────────────────────────────────────────────
        const list = document.getElementById("active-responders-list");
        if (list) {
            list.innerHTML = responders.length === 0
                ? `<div style="padding:20px;text-align:center;color:var(--text-muted);font-size:0.75rem;">No live responders registered yet.</div>`
                : responders.map(buildFleetCard).join("");
        }

        // ── Header active-units count ────────────────────────────────────────
        const online = responders.filter(r => r.status === "ONLINE").length;
        document.querySelectorAll(".telemetry-summary strong").forEach((el, i) => {
            if (i === 1) el.textContent = online;
        });

        const badge = document.querySelector(".fleet-panel .panel-badge");
        if (badge) badge.textContent = `${responders.length} MONITORED`;

        // ── Map markers ─────────────────────────────────────────────────────
        const seen = new Set();

        responders.forEach(r => {
            if (r.last_lat == null || r.last_lon == null) return;
            const id  = r.responder_user_id;
            const pos = [r.last_lat, r.last_lon];
            seen.add(id);

            if (responderMarkers[id]) {
                responderMarkers[id].setLatLng(pos);
            } else {
                responderMarkers[id] = L.marker(pos, { icon: makeResponderIcon() })
                    .bindTooltip(`<strong>${id}</strong><br/>${r.district_id || ""}`, { direction: "top" })
                    .addTo(map);
            }
        });

        // Remove markers for responders no longer in the list
        Object.keys(responderMarkers).forEach(id => {
            if (!seen.has(id)) {
                map.removeLayer(responderMarkers[id]);
                delete responderMarkers[id];
            }
        });

    } catch (err) {
        console.warn("[FleetRenderer] Backend unreachable:", err.message);
    }
}

// ─────────────────────────────────────────────────────────────────────────────
//  FEATURE 2 — Auto Risk Scheduler
// ─────────────────────────────────────────────────────────────────────────────

let schedulerRunning    = false;
let schedulerIntervalId = null;
const SCHEDULER_INTERVAL_MS = 30000;

function updateSchedulerBadge(running, zone, score) {
    const badge = document.getElementById("scheduler-status-badge");
    if (!badge) return;
    if (!running)      { badge.style.color = "var(--text-muted)";  badge.textContent = "AUTO: OFF";        return; }
    if (!zone)         { badge.style.color = "var(--color-blue)";  badge.textContent = "AUTO: SCANNING…";  return; }
    badge.style.color   = score >= 0.75 ? "var(--color-red)" : "var(--color-green)";
    badge.textContent   = `AUTO: ${zone} → ${(score * 100).toFixed(0)}%`;
}

/** Drop a temporary red incident marker on the real map and remove after 10s */
function flashIncidentOnMap(lat, lon, zoneName, score) {
    if (!map) return;
    const marker = L.marker([lat, lon], { icon: makeIncidentIcon() })
        .bindPopup(`
            <strong style="color:#FF3B30">⚠ CRITICAL ALERT</strong><br/>
            <b>${zoneName}</b><br/>
            Risk Score: <b>${(score * 100).toFixed(1)}%</b>
        `, { autoClose: false })
        .addTo(map);

    marker.openPopup();
    map.panTo([lat, lon], { animate: true, duration: 0.8 });

    // Auto-remove after 10 seconds
    setTimeout(() => {
        map.removeLayer(marker);
    }, 10000);
}

async function schedulerTick() {
    const zone = BENGALURU_ZONES[Math.floor(Math.random() * BENGALURU_ZONES.length)];
    updateSchedulerBadge(true, null, null);
    console.log(`[RiskScheduler] Scoring: ${zone.name}`);

    try {
        const mlRes = await fetch(`${ML_ENGINE_URL}/predict/risk`, {
            method:  "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                hour_of_day:                  zone.hour,
                day_of_week:                  zone.dow,
                road_speed_limit:             zone.speed_limit,
                vehicle_speed:                zone.vehicle_speed,
                weather_code:                 zone.weather,
                visibility_km:                zone.visibility,
                traffic_density:              zone.traffic,
                historical_accidents_norm:    zone.hist,
                time_since_last_incident_hrs: zone.last_inc,
            }),
        });

        const ml    = await mlRes.json();
        const score = ml.risk_score;
        const crit  = ml.above_threshold;

        console.log(`[RiskScheduler] ${zone.name}: score=${score}, critical=${crit}`);
        updateSchedulerBadge(true, zone.name, score);

        if (crit) {
            // Flash on map
            flashIncidentOnMap(zone.lat, zone.lon, zone.name, score);

            // Fire alert via backend → SocketIO → dashboard alert card
            await fetch(`${BACKEND_URL}/api/incidents/critical`, {
                method:  "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    district_id:    "PAC-CENTRAL",
                    zone_name:      zone.name,
                    lat:            zone.lat,
                    lon:            zone.lon,
                    message:        `Auto-detected high crash risk at ${zone.name}`,
                    severity:       "critical",
                    probability:    score,
                    response_route: `Dispatch nearest unit to ${zone.name}`,
                }),
            });
        }

    } catch (err) {
        console.warn("[RiskScheduler] Tick error:", err.message);
        updateSchedulerBadge(true, "ERROR", 0);
    }
}

function startScheduler() {
    if (schedulerRunning) return;
    schedulerRunning = true;
    updateSchedulerBadge(true, null, null);
    schedulerTick();
    schedulerIntervalId = setInterval(schedulerTick, SCHEDULER_INTERVAL_MS);
    document.getElementById("scheduler-toggle-btn").textContent = "STOP AUTO SCAN";
    document.getElementById("scheduler-toggle-btn").style.color = "var(--color-red)";
}

function stopScheduler() {
    schedulerRunning = false;
    clearInterval(schedulerIntervalId);
    updateSchedulerBadge(false, null, null);
    document.getElementById("scheduler-toggle-btn").textContent = "START AUTO SCAN";
    document.getElementById("scheduler-toggle-btn").style.color = "var(--text-primary)";
}

// ─────────────────────────────────────────────────────────────────────────────
//  Inject scheduler toggle into header
// ─────────────────────────────────────────────────────────────────────────────

function injectSchedulerToggle() {
    const header = document.querySelector(".telemetry-summary");
    if (!header) return;
    const wrapper = document.createElement("div");
    wrapper.style.cssText = "display:flex;align-items:center;gap:8px;";
    wrapper.innerHTML = `
        <span id="scheduler-status-badge"
              style="font-size:0.68rem;font-weight:700;color:var(--text-muted);
                     font-family:var(--font-mono);letter-spacing:0.02em;">AUTO: OFF</span>
        <button id="scheduler-toggle-btn"
                style="font-size:0.65rem;font-weight:700;padding:4px 10px;
                       border-radius:6px;border:1px solid var(--border-glass);
                       background:#fff;color:var(--text-primary);cursor:pointer;">
            START AUTO SCAN
        </button>`;
    header.appendChild(wrapper);

    document.getElementById("scheduler-toggle-btn").addEventListener("click", function () {
        schedulerRunning ? stopScheduler() : startScheduler();
    });
}

// ─────────────────────────────────────────────────────────────────────────────
//  Boot
// ─────────────────────────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
    initMap();
    injectSchedulerToggle();

    refreshFleet();
    setInterval(refreshFleet, 5000);

    console.log("[MapRenderer] Leaflet OSM map + live fleet polling started.");
});