import json
from datetime import datetime, timezone
from urllib.parse import urlparse
from workers import WorkerEntrypoint, Response

# ==========================================
# CONFIGURATION & HARDCODED SECRET
# ==========================================
HARDCODED_REGISTRY_SECRET = "YOUR_HARDCODED_SECRET_HERE"
KV_KEY_CURRENT = "current"
KV_KEY_HISTORY = "history"
# ==========================================


def make_json_response(data: dict, status: int = 200, headers: dict = None) -> Response:
    resp_headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Cache-Control": "no-store",
    }
    if headers:
        resp_headers.update(headers)
    return Response(json.dumps(data), status=status, headers=resp_headers)


class Default(WorkerEntrypoint):
    def is_authorized(self, request) -> bool:
        secret = HARDCODED_REGISTRY_SECRET or getattr(self.env, "REGISTRY_SECRET", None)
        auth_header = request.headers.get("X-Registry-Key")
        return bool(secret and auth_header and auth_header == secret)

    async def fetch(self, request):
        try:
            parsed_req_url = urlparse(request.url)
            path = parsed_req_url.path.rstrip("/") + "/"
            method = request.method.upper()

            # Protected history route
            if path == "/api/endpoint/history/":
                if method == "GET":
                    return await self.handle_get_history(request)
                return make_json_response(
                    {"error": f"Method {method} Not Allowed"},
                    status=405,
                    headers={"Allow": "GET"}
                )

            # Core registry routes
            if path == "/api/endpoint/":
                if method == "GET":
                    return await self.handle_get_current()
                elif method == "POST":
                    return await self.handle_post(request)
                else:
                    return make_json_response(
                        {"error": f"Method {method} Not Allowed"},
                        status=405,
                        headers={"Allow": "GET, POST"}
                    )

            return make_json_response({"error": "Not Found"}, status=404)

        except Exception as err:
            return make_json_response({"error": f"Internal Server Error: {str(err)}"}, status=500)

    async def handle_get_current(self) -> Response:
        try:
            raw_record = await self.env.NGROK_REGISTRY.get(KV_KEY_CURRENT)
        except Exception:
            return make_json_response({"error": "Failed to read from KV store"}, status=500)

        if not raw_record:
            return make_json_response({"error": "No URL registered yet"}, status=404)

        try:
            data = json.loads(raw_record)
            return make_json_response({
                "url": data.get("url"),
                "updated_at": data.get("updated_at")
            }, status=200)
        except Exception:
            return make_json_response({"error": "Corrupted record in KV store"}, status=500)

    async def handle_get_history(self, request) -> Response:
        # Enforce authentication on history retrieval
        if not self.is_authorized(request):
            return make_json_response({"error": "Unauthorized"}, status=401)

        try:
            raw_history = await self.env.NGROK_REGISTRY.get(KV_KEY_HISTORY)
        except Exception:
            return make_json_response({"error": "Failed to read history from KV store"}, status=500)

        if not raw_history:
            return make_json_response({"history": []}, status=200)

        try:
            history_list = json.loads(raw_history)
            return make_json_response({"history": history_list}, status=200)
        except Exception:
            return make_json_response({"error": "Corrupted history record in KV store"}, status=500)

    async def handle_post(self, request) -> Response:
        # Enforce authentication on publishing
        if not self.is_authorized(request):
            return make_json_response({"error": "Unauthorized"}, status=401)

        try:
            body_text = await request.text()
            payload = json.loads(body_text)
        except Exception:
            return make_json_response({"error": "Malformed JSON payload"}, status=400)

        url = payload.get("url")
        if not url or not isinstance(url, str):
            return make_json_response({"error": "Field 'url' is required and must be a string"}, status=400)

        parsed = urlparse(url)
        if parsed.scheme.lower() != "https" or not parsed.netloc:
            return make_json_response({"error": "URL must be a valid HTTPS URL with a hostname"}, status=400)

        updated_at = datetime.now(timezone.utc).isoformat()
        new_entry = {"url": url, "updated_at": updated_at}
        record_value = json.dumps(new_entry)

        try:
            # 1. Update current pointer
            await self.env.NGROK_REGISTRY.put(KV_KEY_CURRENT, record_value)

            # 2. Append to history list
            raw_history = await self.env.NGROK_REGISTRY.get(KV_KEY_HISTORY)
            history_list = json.loads(raw_history) if raw_history else []
            history_list.append(new_entry)

            # Keep the last 50 updates
            if len(history_list) > 50:
                history_list = history_list[-50:]

            await self.env.NGROK_REGISTRY.put(KV_KEY_HISTORY, json.dumps(history_list))

        except Exception:
            return make_json_response({"error": "Failed to update KV store"}, status=500)

        return make_json_response({
            "ok": True,
            "url": url,
            "updated_at": updated_at
        }, status=200)