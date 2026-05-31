import time
import random
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, join_room

app = Flask(__name__)
app.config["SECRET_KEY"] = "dev-secret-key"

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="threading"
)

responders = {}
trails = {}

EVENT_CRITICAL_INCIDENT = "critical_incident"
EVENT_RESPONDER_STATUS_UPDATE = "responder_status_update"
EVENT_RESPONDER_LOCATION_UPDATE = "responder_location_update"


@socketio.on("connect")
def handle_connect():
    district_id = request.args.get("district_id", "NATIONAL")
    join_room(district_id)
    print(f"Client connected to district room: {district_id}")


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/api/responders/heartbeat", methods=["POST"])
def responder_heartbeat():
    payload = request.get_json(force=True)

    responder_user_id = payload.get("responder_user_id")
    district_id = payload.get("district_id", "NATIONAL")

    if not responder_user_id:
        return jsonify({"error": "responder_user_id is required"}), 400

    responders[responder_user_id] = {
        "responder_user_id": responder_user_id,
        "district_id": district_id,
        "status": "ONLINE",
        "timestamp_last_ping": time.time()
    }

    socketio.emit(
        EVENT_RESPONDER_STATUS_UPDATE,
        {
            "responder_user_id": responder_user_id,
            "district_id": district_id,
            "status": "ONLINE"
        },
        room=district_id
    )

    return jsonify({
        "status": "heartbeat_received",
        "responder": responders[responder_user_id]
    })


@app.route("/api/responders/location", methods=["POST"])
def responder_location():
    payload = request.get_json(force=True)

    responder_user_id = payload.get("responder_user_id")
    district_id = payload.get("district_id", "NATIONAL")
    lat = payload.get("lat")
    lon = payload.get("lon")

    if not responder_user_id:
        return jsonify({"error": "responder_user_id is required"}), 400

    if lat is None or lon is None:
        return jsonify({"error": "lat and lon are required"}), 400

    lat = float(lat)
    lon = float(lon)

    responders[responder_user_id] = {
        "responder_user_id": responder_user_id,
        "district_id": district_id,
        "status": "ONLINE",
        "timestamp_last_ping": time.time(),
        "last_lat": lat,
        "last_lon": lon
    }

    if responder_user_id not in trails:
        trails[responder_user_id] = []

    trails[responder_user_id].append({
        "lat": lat,
        "lon": lon,
        "timestamp": time.time()
    })

    fake_lat = lat + random.uniform(-0.002, 0.002)
    fake_lon = lon + random.uniform(-0.002, 0.002)

    socketio.emit(
        EVENT_RESPONDER_LOCATION_UPDATE,
        {
            "responder_user_id": responder_user_id,
            "district_id": district_id,
            "lat": fake_lat,
            "lon": fake_lon,
            "status": "ONLINE"
        },
        room=district_id
    )

    return jsonify({
        "status": "location_updated",
        "responder": responders[responder_user_id],
        "public_location": {
            "lat": fake_lat,
            "lon": fake_lon
        }
    })


@app.route("/api/responders", methods=["GET"])
def get_responders():
    district_id = request.args.get("district_id")

    result = list(responders.values())

    if district_id:
        result = [
            responder for responder in result
            if responder.get("district_id") == district_id
        ]

    return jsonify({"responders": result})


@app.route("/api/responders/<responder_user_id>/trail", methods=["GET"])
def get_trail(responder_user_id):
    return jsonify({
        "responder_user_id": responder_user_id,
        "trail": trails.get(responder_user_id, [])
    })


@app.route("/api/incidents/critical", methods=["POST"])
def critical_incident():
    payload = request.get_json(force=True)

    district_id = payload.get("district_id", "NATIONAL")

    socketio.emit(
        EVENT_CRITICAL_INCIDENT,
        payload,
        room=district_id
    )

    return jsonify({
        "status": "sent",
        "event": EVENT_CRITICAL_INCIDENT,
        "district_id": district_id
    })


if __name__ == "__main__":
    socketio.run(
        app,
        host="127.0.0.1",
        port=5050,
        debug=True,
        use_reloader=False,
        allow_unsafe_werkzeug=True
    )