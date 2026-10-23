import json
import os
from datetime import datetime, timezone
from urllib.parse import urlparse
from flask import Flask, request, jsonify, make_response

app = Flask(__name__)

# ==========================================
# CONFIGURATION
# ==========================================
HARDCODED_REGISTRY_SECRET = "SUPERUSER_secret_REGISTERED_under_181620070611"
STORAGE_FILE = "registry_data.json"
MAX_HISTORY_ENTRIES = 50
# ==========================================


def load_storage():
    """Reads data from the local JSON file or returns defaults."""
    if not os.path.exists(STORAGE_FILE):
        return {"current": None, "history": []}
    try:
        with open(STORAGE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"current": None, "history": []}


def save_storage(data):
    """Writes updated data to the local JSON file."""
    with open(STORAGE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def json_response(payload, status=200):
    """Helper to ensure Cache-Control: no-store and correct content type."""
    resp = make_response(jsonify(payload), status)
    resp.headers["Cache-Control"] = "no-store"
    return resp


def is_authorized():
    secret = os.environ.get("REGISTRY_SECRET", HARDCODED_REGISTRY_SECRET)
    auth_header = request.headers.get("X-Registry-Key")
    return bool(secret and auth_header and auth_header == secret)


@app.route("/api/endpoint/", methods=["GET", "POST"])
def endpoint_current():
    if request.method == "GET":
        data = load_storage()
        current = data.get("current")
        if not current:
            return json_response({"error": "No URL registered yet"}, 404)
        return json_response(current, 200)

    # POST - Publish new URL
    if not is_authorized():
        return json_response({"error": "Unauthorized"}, 401)

    payload = request.get_json(silent=True)
    if not payload or not isinstance(payload, dict):
        return json_response({"error": "Malformed JSON payload"}, 400)

    url = payload.get("url")
    if not url or not isinstance(url, str):
        return json_response({"error": "Field 'url' is required and must be a string"}, 400)

    parsed = urlparse(url)
    if parsed.scheme.lower() != "https" or not parsed.netloc:
        return json_response({"error": "URL must be a valid HTTPS URL with a hostname"}, 400)

    updated_at = datetime.now(timezone.utc).isoformat()
    new_entry = {"url": url, "updated_at": updated_at}

    try:
        data = load_storage()
        data["current"] = new_entry
        data.setdefault("history", []).append(new_entry)

        # Cap history to prevent unbounded file growth
        if len(data["history"]) > MAX_HISTORY_ENTRIES:
            data["history"] = data["history"][-MAX_HISTORY_ENTRIES:]

        save_storage(data)
    except Exception as err:
        return json_response({"error": f"Failed to persist record: {str(err)}"}, 500)

    return json_response({"ok": True, "url": url, "updated_at": updated_at}, 200)


@app.route("/api/endpoint/history/", methods=["GET"])
def endpoint_history():
    if not is_authorized():
        return json_response({"error": "Unauthorized"}, 401)

    data = load_storage()
    return json_response({"history": data.get("history", [])}, 200)


@app.errorhandler(405)
def method_not_allowed(e):
    return json_response({"error": "Method Not Allowed"}, 405)


@app.errorhandler(404)
def not_found(e):
    return json_response({"error": "Not Found"}, 404)


if __name__ == "__main__":
    # Runs locally on port 5000
    app.run(host="0.0.0.0", port=5000, debug=False)