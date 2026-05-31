import os
import sys
import json
import logging
import threading
from datetime import datetime

import numpy as np
import pandas as pd
from flask import Flask, request, jsonify
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
import joblib

# path bootstrap so imports work from /app (Docker WORKDIR) 
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from core_config.global_constants import (
    RISK_THRESHOLD_HIGH,
    SPATIAL_SCAN_RADIUS_KM,
    RUN_ENVIRONMENT,
)
from data_ml_engine.scorer.gap_analyzer import TargetGapScorer

# logging 
logging.basicConfig(
    level=logging.DEBUG if RUN_ENVIRONMENT == "DEVELOPMENT" else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
log = logging.getLogger("ml_api_server")

# Flask app 
app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False

# global model state 
MODEL_PATH = os.path.join(os.path.dirname(__file__), "risk_model.joblib")
_model_lock = threading.Lock()
_risk_pipeline: Pipeline | None = None
_model_meta: dict = {"trained_at": None, "samples": 0, "report": {}}

gap_scorer = TargetGapScorer()



#  Model helpers

def _build_pipeline() -> Pipeline:
    """Construct a fresh sklearn Pipeline."""
    return Pipeline([
        ("scaler", StandardScaler()),
        ("clf", GradientBoostingClassifier(
            n_estimators=150,
            max_depth=4,
            learning_rate=0.08,
            subsample=0.85,
            random_state=42,
        )),
    ])


def _load_model() -> Pipeline | None:
    """Load a persisted model from disk, or return None."""
    if os.path.exists(MODEL_PATH):
        try:
            pipeline = joblib.load(MODEL_PATH)
            log.info("Loaded persisted model from %s", MODEL_PATH)
            return pipeline
        except Exception as exc:
            log.warning("Could not load saved model: %s", exc)
    return None


def _synthetic_training_data(n: int = 2000) -> tuple[np.ndarray, np.ndarray]:
    """
    Generate synthetic training data that mimics real accident-risk telemetry.

    Features (9 columns)
    ---------------------
    0  hour_of_day       — 0–23
    1  day_of_week       — 0 (Mon) … 6 (Sun)
    2  road_speed_limit  — km/h
    3  vehicle_speed     — km/h
    4  weather_code      — 0 clear, 1 rain, 2 fog, 3 ice
    5  visibility_km     — 0–10
    6  traffic_density   — 0.0–1.0
    7  historical_acci   — past incidents in zone (normalised 0–1)
    8  time_since_last   — hours since last incident in zone
    """
    rng = np.random.default_rng(0)
    hour          = rng.integers(0, 24, n)
    dow           = rng.integers(0, 7, n)
    speed_limit   = rng.choice([30, 40, 50, 60, 80, 100, 120], n)
    vehicle_speed = np.clip(speed_limit + rng.normal(0, 15, n), 0, 180)
    weather       = rng.choice([0, 1, 2, 3], n, p=[0.6, 0.25, 0.1, 0.05])
    visibility    = np.clip(10 - weather * rng.uniform(1, 3, n), 0.5, 10)
    traffic       = rng.uniform(0, 1, n)
    hist_acci     = rng.uniform(0, 1, n)
    time_since    = rng.exponential(scale=12, size=n)

    X = np.column_stack([
        hour, dow, speed_limit, vehicle_speed,
        weather, visibility, traffic, hist_acci, time_since,
    ]).astype(float)

    # Label: high risk if speeding + bad weather + dense traffic + past incidents
    speeding    = (vehicle_speed - speed_limit) > 10
    bad_weather = weather >= 2
    dense       = traffic > 0.7
    has_history = hist_acci > 0.6
    night_peak  = ((hour >= 22) | (hour <= 5))

    score = (
        speeding.astype(float) * 0.35
        + bad_weather.astype(float) * 0.25
        + dense.astype(float) * 0.15
        + has_history.astype(float) * 0.15
        + night_peak.astype(float) * 0.10
    )
    y = (score + rng.uniform(-0.1, 0.1, n) > 0.45).astype(int)

    return X, y


def _train_and_persist(X: np.ndarray, y: np.ndarray) -> dict:
    """Fit the pipeline, persist it, and return a metrics dict."""
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )
    pipeline = _build_pipeline()
    pipeline.fit(X_train, y_train)

    y_pred = pipeline.predict(X_test)
    report = classification_report(y_test, y_pred, output_dict=True)

    joblib.dump(pipeline, MODEL_PATH)
    log.info("Model trained and saved → %s", MODEL_PATH)

    return {
        "trained_at": datetime.utcnow().isoformat() + "Z",
        "samples": int(len(X)),
        "report": report,
    }


def _ensure_model_loaded():
    """Lazy-initialise: load from disk or train on synthetic data."""
    global _risk_pipeline, _model_meta
    with _model_lock:
        if _risk_pipeline is None:
            _risk_pipeline = _load_model()
            if _risk_pipeline is None:
                log.info("No saved model found — training on synthetic data…")
                X, y = _synthetic_training_data()
                _model_meta = _train_and_persist(X, y)
                _risk_pipeline = joblib.load(MODEL_PATH)
                log.info("Initial synthetic training complete.")



#  Request validation helpers


REQUIRED_FEATURES = [
    "hour_of_day", "day_of_week", "road_speed_limit", "vehicle_speed",
    "weather_code", "visibility_km", "traffic_density",
    "historical_accidents_norm", "time_since_last_incident_hrs",
]


def _extract_feature_vector(payload: dict) -> np.ndarray:
    """Pull REQUIRED_FEATURES from payload dict into a (1, 9) array."""
    missing = [f for f in REQUIRED_FEATURES if f not in payload]
    if missing:
        raise ValueError(f"Missing feature fields: {missing}")
    return np.array([[float(payload[f]) for f in REQUIRED_FEATURES]])



#  Routes


@app.route("/health", methods=["GET"])
def health():
    """Liveness + readiness probe."""
    return jsonify({
        "status": "ok",
        "service": "precrash_ml_engine",
        "environment": RUN_ENVIRONMENT,
        "model_ready": _risk_pipeline is not None,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }), 200


@app.route("/predict/risk", methods=["POST"])
def predict_risk():
    """
    Predict crash-risk score for a single telemetry snapshot.

    Request body (JSON)
    -------------------
    {
      "hour_of_day": 22,
      "day_of_week": 5,
      "road_speed_limit": 60,
      "vehicle_speed": 85,
      "weather_code": 1,
      "visibility_km": 6.5,
      "traffic_density": 0.72,
      "historical_accidents_norm": 0.55,
      "time_since_last_incident_hrs": 3.2
    }

    Response
    --------
    {
      "risk_score": 0.84,
      "risk_label": "HIGH",
      "above_threshold": true
    }
    """
    _ensure_model_loaded()
    body = request.get_json(silent=True)
    if not body:
        return jsonify({"error": "Empty or non-JSON request body"}), 400

    try:
        X = _extract_feature_vector(body)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 422

    with _model_lock:
        proba = _risk_pipeline.predict_proba(X)[0]

    risk_score = float(proba[1])  # P(high-risk class)
    above = risk_score >= RISK_THRESHOLD_HIGH

    return jsonify({
        "risk_score": round(risk_score, 4),
        "risk_label": "HIGH" if above else "LOW",
        "above_threshold": above,
        "threshold_used": RISK_THRESHOLD_HIGH,
    }), 200


@app.route("/predict/gap", methods=["POST"])
def predict_gap():
    """
    Compute the Responder Gap Index for a live incident coordinate.

    Request body (JSON)
    -------------------
    {
      "hazard_lat": 12.9716,
      "hazard_lon": 77.5946,
      "risk_score": 0.82,          ← from /predict/risk, or supplied directly
      "active_responders": [
        {"lat": 12.975, "lon": 77.590, "unit_type": "AMBULANCE"},
        {"lat": 12.960, "lon": 77.600, "unit_type": "POLICE"}
      ]
    }

    Response
    --------
    {
      "gap_index": 0.67,
      "critical": true,
      "responders_in_radius": 1,
      "scan_radius_km": 5.0
    }
    """
    body = request.get_json(silent=True)
    if not body:
        return jsonify({"error": "Empty or non-JSON request body"}), 400

    required = ["hazard_lat", "hazard_lon", "risk_score", "active_responders"]
    missing = [k for k in required if k not in body]
    if missing:
        return jsonify({"error": f"Missing fields: {missing}"}), 422

    try:
        hazard_lat = float(body["hazard_lat"])
        hazard_lon = float(body["hazard_lon"])
        risk_score = float(body["risk_score"])
        responders = body["active_responders"]

        if not isinstance(responders, list):
            raise ValueError("active_responders must be a list")

        gap = gap_scorer.evaluate_responder_gap_index(
            hazard_lat, hazard_lon, risk_score, responders
        )

        # Count how many responders are actually within the scan radius
        in_radius = sum(
            1 for r in responders
            if gap_scorer.compute_haversine_distance(
                hazard_lat, hazard_lon, r["lat"], r["lon"]
            ) <= SPATIAL_SCAN_RADIUS_KM
        )

    except (ValueError, KeyError, TypeError) as exc:
        return jsonify({"error": str(exc)}), 422

    return jsonify({
        "gap_index": round(gap, 4),
        "critical": gap_scorer.is_critical(gap),
        "responders_in_radius": in_radius,
        "scan_radius_km": SPATIAL_SCAN_RADIUS_KM,
    }), 200


@app.route("/predict/batch_zones", methods=["POST"])
def predict_batch_zones():
    """
    Rank multiple hazard zones by Responder Gap Index (most exposed first).

    Request body (JSON)
    -------------------
    {
      "hazard_zones": [
        {"zone_id": "Z1", "lat": 12.97, "lon": 77.59, "risk_score": 0.80},
        {"zone_id": "Z2", "lat": 12.93, "lon": 77.63, "risk_score": 0.55}
      ],
      "active_responders": [
        {"lat": 12.975, "lon": 77.590}
      ]
    }

    Response
    --------
    { "ranked_zones": [ { ...zone + gap_index + critical }, ... ] }
    """
    body = request.get_json(silent=True)
    if not body:
        return jsonify({"error": "Empty or non-JSON request body"}), 400

    try:
        zones = body["hazard_zones"]
        responders = body.get("active_responders", [])
        ranked = gap_scorer.rank_hazard_zones(zones, responders)
    except (KeyError, TypeError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 422

    return jsonify({"ranked_zones": ranked}), 200


@app.route("/train", methods=["POST"])
def train_model():
    """
    (Re)train the risk model.

    Accepts an optional JSON body with a 'dataset' key containing a list of
    records.  Each record must include the 9 feature keys plus a 'label' key
    (0 or 1).  If no dataset is provided, the model is retrained on fresh
    synthetic data.

    Response
    --------
    { "status": "trained", "samples": N, "trained_at": "...", "report": {...} }
    """
    global _risk_pipeline, _model_meta

    body = request.get_json(silent=True) or {}
    dataset = body.get("dataset")

    try:
        if dataset:
            df = pd.DataFrame(dataset)
            X = df[REQUIRED_FEATURES].values.astype(float)
            y = df["label"].values.astype(int)
            log.info("Training on %d supplied records…", len(X))
        else:
            log.info("No dataset provided — generating synthetic training data…")
            X, y = _synthetic_training_data(n=3000)

        meta = _train_and_persist(X, y)

        with _model_lock:
            _risk_pipeline = joblib.load(MODEL_PATH)
            _model_meta = meta

    except Exception as exc:
        log.exception("Training failed")
        return jsonify({"error": str(exc)}), 500

    return jsonify({"status": "trained", **meta}), 200


@app.route("/model/info", methods=["GET"])
def model_info():
    """Return metadata about the currently loaded model."""
    _ensure_model_loaded()
    return jsonify({
        "model_ready": _risk_pipeline is not None,
        "risk_threshold": RISK_THRESHOLD_HIGH,
        "scan_radius_km": SPATIAL_SCAN_RADIUS_KM,
        "feature_columns": REQUIRED_FEATURES,
        **_model_meta,
    }), 200



#  Entry point


if __name__ == "__main__":
    log.info("PreCrash SoS — ML Engine starting on port 8001 [%s]", RUN_ENVIRONMENT)
    _ensure_model_loaded()          # warm up the model before accepting traffic
    app.run(host="0.0.0.0", port=8001, debug=(RUN_ENVIRONMENT == "DEVELOPMENT"))