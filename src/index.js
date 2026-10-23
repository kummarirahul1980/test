const HARDCODED_REGISTRY_SECRET = "SUPERUSER_secret_REGISTERED_under_181620070611";
const KV_KEY_CURRENT = "current";
const KV_KEY_HISTORY = "history";
const MAX_HISTORY_ENTRIES = 50;

function jsonResponse(data, status = 200, headers = {}) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "no-store",
      ...headers,
    },
  });
}

function isAuthorized(request, env) {
  const secret = env.REGISTRY_KEY || env.REGISTRY_SECRET || HARDCODED_REGISTRY_SECRET;
  const authHeader = request.headers.get("X-Registry-Key");
  return Boolean(secret && authHeader && authHeader === secret);
}

export default {
  async fetch(request, env, ctx) {
    try {
      const url = new URL(request.url);
      const path = url.pathname.replace(/\/+$/, "") + "/";
      const method = request.method.toUpperCase();

      // Route: GET /api/endpoint/history/
      if (path === "/api/endpoint/history/") {
        if (method !== "GET") {
          return jsonResponse({ error: "Method Not Allowed" }, 405, { Allow: "GET" });
        }
        if (!isAuthorized(request, env)) {
          return jsonResponse({ error: "Unauthorized" }, 401);
        }

        const rawHistory = await env.NGROK_REGISTRY.get(KV_KEY_HISTORY);
        const historyList = rawHistory ? JSON.parse(rawHistory) : [];
        return jsonResponse({ history: historyList }, 200);
      }

      // Route: /api/endpoint/
      if (path === "/api/endpoint/") {
        if (method === "GET") {
          const rawRecord = await env.NGROK_REGISTRY.get(KV_KEY_CURRENT);
          if (!rawRecord) {
            return jsonResponse({ error: "No URL registered yet" }, 404);
          }
          return jsonResponse(JSON.parse(rawRecord), 200);
        }

        if (method === "POST") {
          if (!isAuthorized(request, env)) {
            return jsonResponse({ error: "Unauthorized" }, 401);
          }

          let payload;
          try {
            payload = await request.json();
          } catch {
            return jsonResponse({ error: "Malformed JSON payload" }, 400);
          }

          const targetUrl = payload?.url;
          if (!targetUrl || typeof targetUrl !== "string") {
            return jsonResponse({ error: "Field 'url' is required and must be a string" }, 400);
          }

          let parsedTarget;
          try {
            parsedTarget = new URL(targetUrl);
          } catch {
            return jsonResponse({ error: "URL must be a valid HTTPS URL with a hostname" }, 400);
          }

          if (parsedTarget.protocol !== "https:" || !parsedTarget.hostname) {
            return jsonResponse({ error: "URL must be a valid HTTPS URL with a hostname" }, 400);
          }

          const updatedAt = new Date().toISOString();
          const newEntry = { url: targetUrl, updated_at: updatedAt };

          // 1. Update current
          await env.NGROK_REGISTRY.put(KV_KEY_CURRENT, JSON.stringify(newEntry));

          // 2. Append to history list
          const rawHistory = await env.NGROK_REGISTRY.get(KV_KEY_HISTORY);
          let historyList = rawHistory ? JSON.parse(rawHistory) : [];
          historyList.push(newEntry);

          if (historyList.length > MAX_HISTORY_ENTRIES) {
            historyList = historyList.slice(-MAX_HISTORY_ENTRIES);
          }

          await env.NGROK_REGISTRY.put(KV_KEY_HISTORY, JSON.stringify(historyList));

          return jsonResponse({ ok: true, url: targetUrl, updated_at: updatedAt }, 200);
        }

        return jsonResponse({ error: "Method Not Allowed" }, 405, { Allow: "GET, POST" });
      }

      return jsonResponse({ error: "Not Found" }, 404);
    } catch (err) {
      return jsonResponse({ error: `Internal Server Error: ${err.message}` }, 500);
    }
  },
};