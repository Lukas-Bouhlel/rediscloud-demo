import eventlet
eventlet.monkey_patch()

import json
import os
import re
import threading
from datetime import datetime, timezone

import redis
from flask import Flask, jsonify, request
from flask_socketio import SocketIO, emit
from google.api_core.exceptions import AlreadyExists
from google.cloud import pubsub_v1

app = Flask(__name__, static_folder="static", static_url_path="")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

# Configuration Redis
r = redis.Redis(
    host=os.environ.get("REDIS_HOST", "127.0.0.1"),
    port=int(os.environ.get("REDIS_PORT", 6379)),
    decode_responses=True,
)

# Configuration Pub/Sub
PROJECT_ID = os.environ.get("PROJECT_ID", "test-project")
TOPIC_ID = os.environ.get("PUBSUB_TOPIC", "redis-updates")
SERVER_ID = os.environ.get("HOSTNAME", "local")

publisher = pubsub_v1.PublisherClient()
subscriber = pubsub_v1.SubscriberClient()


def _sanitize_subscription_id(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9\-_.]", "-", value)
    return safe[:255]


SUBSCRIPTION_ID = os.environ.get(
    "PUBSUB_SUBSCRIPTION",
    _sanitize_subscription_id(f"{TOPIC_ID}-{SERVER_ID}"),
)

TOPIC_PATH = publisher.topic_path(PROJECT_ID, TOPIC_ID)
SUBSCRIPTION_PATH = subscriber.subscription_path(PROJECT_ID, SUBSCRIPTION_ID)


def ensure_topic_and_subscription() -> None:
    try:
        publisher.create_topic(request={"name": TOPIC_PATH})
    except AlreadyExists:
        pass

    try:
        subscriber.create_subscription(
            request={"name": SUBSCRIPTION_PATH, "topic": TOPIC_PATH}
        )
    except AlreadyExists:
        pass


def load_initial_state() -> dict:
    result = {}
    cursor = 0
    while True:
        cursor, keys = r.scan(cursor=cursor, match="event:*", count=100)
        for key in keys:
            value = r.get(key)
            if value:
                result[key] = {
                    "data": json.loads(value),
                    "ttl_remaining_seconds": r.ttl(key),
                }
        if cursor == 0:
            break
    return result


@socketio.on("connect")
def on_connect():
    state = load_initial_state()
    emit(
        "initial_state",
        {"server_id": SERVER_ID, "count": len(state), "entries": state},
    )


def handle_pubsub_message(message: pubsub_v1.subscriber.message.Message) -> None:
    try:
        redis_key = message.data.decode("utf-8")
        value = r.get(redis_key)
        payload = {
            "server_id": SERVER_ID,
            "redis_key": redis_key,
            "data": json.loads(value) if value else None,
            "ttl_remaining_seconds": r.ttl(redis_key),
        }
        socketio.emit("update", payload)
        message.ack()
    except Exception as exc:
        print(f"Pub/Sub handler error: {exc}")
        message.nack()


def start_pubsub_listener() -> None:
    ensure_topic_and_subscription()

    def _run() -> None:
        future = subscriber.subscribe(SUBSCRIPTION_PATH, callback=handle_pubsub_message)
        try:
            future.result()
        except Exception as exc:
            print(f"Pub/Sub listener stopped: {exc}")

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()


start_pubsub_listener()


@app.route("/")
def index():
    return app.send_static_file("index.html")


@app.route("/publish", methods=["POST"])
def publish():
    data = request.get_json() or {}
    if "message" not in data:
        return jsonify({"error": "Champ 'message' requis"}), 400

    entry = {
        "message": data["message"],
        "server_id": SERVER_ID,
        "published_at": datetime.now(timezone.utc).isoformat(),
    }

    # 1. Stockage dans Redis (source de verite)
    key = f"event:{SERVER_ID}:{entry['published_at']}"
    r.setex(key, 3600, json.dumps(entry))

    # 2. Diffusion via Pub/Sub (alerte pour les autres instances)
    publisher.publish(TOPIC_PATH, key.encode("utf-8"))

    return jsonify({"status": "published", "redis_key": key, "data": entry})


@app.route("/data")
def data():
    state = load_initial_state()
    return jsonify({"server_id": SERVER_ID, "count": len(state), "entries": state})


@app.route("/health")
def health():
    try:
        r.ping()
        return jsonify({"status": "healthy", "server_id": SERVER_ID, "redis": "connected"})
    except Exception as exc:
        return jsonify({"status": "unhealthy", "error": str(exc)}), 503


if __name__ == "__main__":
    socketio.run(
        app,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8080)),
        debug=os.environ.get("FLASK_DEBUG") == "1",
        use_reloader=False,
    )

