
export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname !== "/api/endpoint/") {
      return Response.json({ error: "Not found" }, { status: 404 });
    }

    if (request.method === "GET") {
      const current = await env.NGROK_REGISTRY.get("current");

      if (!current) {
        return Response.json(
          { error: "No URL published yet" },
          { status: 404 }
        );
      }

      return Response.json(JSON.parse(current), {
        headers: { "Cache-Control": "no-store" }
      });
    }

    if (request.method === "POST") {
      if (request.headers.get("X-Registry-Key") !== env.REGISTRY_SECRET) {
        return Response.json({ error: "Unauthorized" }, { status: 401 });
      }

      let data;
      try {
        data = await request.json();
      } catch {
        return Response.json({ error: "Invalid JSON" }, { status: 400 });
      }

      if (
        typeof data.url !== "string" ||
        !data.url.startsWith("https://")
      ) {
        return Response.json({ error: "Invalid URL" }, { status: 400 });
      }

      const record = {
        url: data.url,
        updated_at: new Date().toISOString()
      };

      await env.NGROK_REGISTRY.put("current", JSON.stringify(record));

      return Response.json({ ok: true });
    }

    return new Response("Method not allowed", {
      status: 405,
      headers: { Allow: "GET, POST" }
    });
  }
};
