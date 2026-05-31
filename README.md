# PreCrash SoS

> **Predicting crashes before they happen. Routing help before it's too late.**

[![Track](https://img.shields.io/badge/Track-RoadSoS-orange)](https://coers.iitm.ac.in)
[![Hackathon](https://img.shields.io/badge/CoERS-IIT%20Madras%202026-blue)](https://coers.iitm.ac.in)
[![Status](https://img.shields.io/badge/Status-Stage%201%20Submitted-green)]()
[![License](https://img.shields.io/badge/License-MIT-lightgrey)]()

---

## The Problem

India recorded **1,68,491 road deaths in 2022** (MoRTH Annual Report). Over 50% of fatalities occur within the golden hour — the critical window where timely intervention determines survival. In rural India, where 65% of fatal accidents happen on national and state highways, average ambulance response times exceed **20 minutes** against an 8-minute golden hour target.

Existing SoS apps are **reactive**. They wait for a victim to dial 112. By the time someone dials, the golden hour is already ticking — and in coverage-gap zones, there is often no one to dial.

**PreCrash SoS is proactive.** It predicts which road segments will be high-risk before a crash occurs, ranks zones by responder exposure, and coordinates a tiered network of verified responders in real time.

---

## System Architecture

Three independently deployable services communicate through well-defined contracts:

```
Browser (localhost:8080)
        │
        ├── HTTP GET :8080          WebSocket / fetch() every 5s
        │                                    │
        ▼                                    ▼
┌─────────────────┐              ┌──────────────────────┐
│   Frontend      │              │   Backend Core       │
│   nginx :8080   │◄────────────►│   Flask + SocketIO   │
│   Leaflet.js    │              │   Port :5050         │
└─────────────────┘              └──────────┬───────────┘
                                            │ REST
                                            ▼
                                 ┌──────────────────────┐
                                 │   ML Engine          │
                                 │   Gradient Boosting  │
                                 │   Port :8001         │
                                 └──────────────────────┘
                                            │
                                 ┌──────────────────────┐
                                 │  Safety Relay Module │
                                 │  heartbeat · fuzzy   │
                                 │  location · breadcrumb│
                                 └──────────────────────┘
```

### ML Engine — `:8001`
- Gradient Boosting Classifier, auto-trains on boot from MoRTH data
- **Inputs:** speed, weather, hour of day, traffic density, historical accident density
- **Output 1:** `risk_score` (0.0 – 1.0) per road segment
- **Output 2:** `Responder Gap Index` per hazard zone
- Zones ranked by gap → dispatchers see the most exposed zone first

### Backend — `:5050`
- Flask + Flask-SocketIO coordination hub
- Tracks active responders (ambulance, police, fire) via heartbeat pings
- Fuzzy GPS anonymization (±200m offset before broadcast)
- WebSocket alert broadcast with **multi-district room routing**
- Breadcrumb trail persistence (GPS logged every 30s from dispatch acceptance)
- **Dead Man Switch** — auto-OFFLINE after 5 missed heartbeat pings

### Frontend — `:8080`
- Vanilla HTML/CSS/JS + Leaflet.js interactive map
- Live hazard zone overlays colour-coded by risk score
- Fleet monitor panel: `STANDBY` / `EN-ROUTE` / `ON-SCENE` status
- Real-time alert cards injected via WebSocket

---

## Project Structure

```
precrash-sos/
├── backend_service/
│   ├── app.py                  # Flask application entry point
│   └── socket_hub.py           # WebSocket room routing & event emission
│
├── core_config/
│   └── global_constants.py     # Shared configuration constants
│
├── dashboard_frontend/
│   ├── Dockerfile
│   ├── static/js/
│   │   ├── map_renderer.js     # Leaflet map, hazard overlays, fleet markers
│   │   └── socket_client.js    # Socket.IO client, alert card injection
│   └── templates/
│       └── portal_index.html   # Single-page dashboard
│
├── data_ml_engine/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── pipeline/
│   │   └── ml_api_server.py    # Flask REST API for risk inference
│   └── scorer/
│       └── gap_analyzer.py     # Responder Gap Index computation
│
├── safety_relay_module/
│   ├── breadcrumb_logger.py    # GPS trail persistence
│   ├── fakedataset.py          # Synthetic MoRTH-distribution training data
│   ├── fuzzy_location.py       # GPS anonymization layer
│   └── heartbeat_monitor.py   # Dead Man Switch logic
│
├── docker-compose.yml          # Production compose
├── docker-compose.temp.yml     # Development/testing compose
└── README.md
```

---

## Quickstart

### Prerequisites
- [Docker](https://www.docker.com/get-started) and Docker Compose
- Or: Python 3.10+ for running services locally

### Run with Docker Compose (recommended)

```bash
git clone https://github.com/khushi-n-murthy/PreCrash-SOS.git
cd PreCrash-SOS
docker-compose up --build
```

Services will be available at:
| Service | URL |
|---|---|
| Dashboard | http://localhost:8080 |
| Backend API | http://localhost:5050 |
| ML Engine API | http://localhost:8001 |

### Run locally (without Docker)

**ML Engine**
```bash
cd data_ml_engine
pip install -r requirements.txt
python pipeline/ml_api_server.py
```

**Backend**
```bash
cd backend_service
pip install flask flask-socketio flask-cors
python app.py
```

**Frontend**
Served automatically by the Flask backend. Open `http://localhost:8080` in your browser.

---

## API Reference

### ML Engine `:8001`

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/predict/risk` | Returns risk score + gap index for a telemetry snapshot |
| `POST` | `/predict/gap` | Returns Responder Gap Index only |
| `POST` | `/predict/batch` | Batch risk assessment across multiple zones |
| `POST` | `/train` | Re-trains model on available data |

**Sample request — `/predict/risk`**
```json
{
  "speed": 82,
  "weather": "rain",
  "hour": 20,
  "day_of_week": 5,
  "traffic_density": 0.74,
  "accident_density": 0.61
}
```

**Sample response**
```json
{
  "risk_score": 0.7561,
  "gap_index": 0.82,
  "tier_activation": "Tier 1 + Tier 2",
  "zone_rank": 1
}
```

### Backend `:5050`

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/responders` | List all active responders |
| `POST` | `/api/responders/location` | Update responder GPS position |
| `POST` | `/api/responders/heartbeat` | Heartbeat ping (keeps unit ONLINE) |
| `POST` | `/api/incidents/critical` | Register a critical incident & trigger WebSocket broadcast |

**WebSocket events emitted by backend**
| Event | Payload | Description |
|---|---|---|
| `critical_incident` | incident object | Broadcast to district room on new alert |
| `responder_status` | `{id, status}` | Unit status change (EN-ROUTE, OFFLINE, etc.) |
| `responder_location` | `{id, lat, lon}` | Fuzzy position update |

---

## Dispatch Logic

Risk scoring drives tiered escalation based on the Responder Gap Index:

| Gap Index | Tiers Activated |
|---|---|
| `< 0.60` | Tier 1 only (ambulance / 108) |
| `0.60 – 0.85` | Tier 1 + Tier 2 (verified volunteers) |
| `> 0.85` | All three tiers activated |

---

## Safety Architecture

> *"The helper can't become the threat."*

| Feature | Status | Description |
|---|---|---|
| **Fuzzy Location** | ✅ Built | Tier 2 & 3 receive a corridor string only (`NH48, approx km 42`). Exact GPS goes only to 112 and Tier 1. |
| **Verified Registry** | ✅ Built | Tier 2 volunteers: Aadhaar-linked, 15-min first-aid cert, vouched by 2 existing responders. |
| **Breadcrumb Trail** | ✅ Built | Responder GPS logged every 30s from dispatch acceptance. Visible to victim's emergency contacts and 112. |
| **Dead Man Switch** | ✅ Built | 5 missed heartbeats → auto-OFFLINE. Victim silent 10 min post-arrival → auto-escalate to 112. |

---

## Implementation Status

### Completed (Sprint 1)
- ML engine boots, auto-trains, and correctly responds to `/predict/risk`
- Backend: SQLite init, heartbeat registration, GPS fuzzy anonymization, breadcrumb persistence, Dead Man Switch, WebSocket emission
- Multi-district room routing verified with two simultaneous dashboard clients
- Frontend: Leaflet map, hazard overlays, fleet monitor panel, real-time alert card injection

### Sprint 2
- [ ] Background APScheduler polling `/predict/risk` every 5 min per active zone (endpoint already built)
- [ ] Connect Leaflet marker layer to live backend responder position feed (WebSocket infra already built)

### Sprint 3
- [ ] Integrate real MoRTH CSV data (replacing synthetic training dataset)
- [ ] Mobile Progressive Web App for field responders
- [ ] Open REST API for NGO partners (Ziqitza, GVK EMRI)

---

## Roadmap

| Phase | Timeline | Milestones |
|---|---|---|
| **Phase 1 — Prototype** | Now | Working ML model, Flask WebSocket backend, Leaflet dashboard. Single-server deployable. |
| **Phase 2 — Pilot** | 3–6 months | Partner with 108 operator in TN/Kerala. 50 verified Tier 2 volunteers on one NH corridor. Real-world accuracy validation. |
| **Phase 3 — Scale** | 6–18 months | State transport dept. road condition feed. Coverage gap dashboard for district officers. Open API for NGOs. Mobile PWA. |

---

## Team

| Name | Role |
|---|---|
| Khushi N Murthy | Data and ML Engine |
| Palak Jangid A | Safety & Relay Protocols |
| Anshi Ijral | Backend Core Architecture |
| Prerna Patro | Frontend Core Integration |

Submitted to **CoERS IIT Madras AI Road Safety Hackathon 2026** — Track: RoadSoS

---

## Data Sources

All external data sources are **free and open**:

| Source | Usage | Cost |
|---|---|---|
| [MoRTH data.gov.in](https://data.gov.in) | Training dataset — accident density by road segment | Free |
| [OpenWeatherMap](https://openweathermap.org/api) | Live weather condition codes | Free tier (1,000 calls/day) |
| [OpenStreetMap Overpass API](https://overpass-api.de) | Road segment geometry for fuzzy location | Free |

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

> *PreCrash SoS is not just a hackathon project. It is a governance tool in the form of an app.*