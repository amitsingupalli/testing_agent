"""Zero-dependency HTTP server for exercising system/performance runners."""

import http from "node:http";

const PORT = Number(process.env.PORT || 8901);

const server = http.createServer((req, res) => {
  const url = new URL(req.url, `http://127.0.0.1:${PORT}`);
  res.setHeader("content-type", "application/json");

  if (url.pathname === "/health" || url.pathname === "/api/health") {
    res.writeHead(200);
    res.end(JSON.stringify({ status: "ok" }));
    return;
  }

  if (url.pathname === "/api/slow") {
    setTimeout(() => {
      res.writeHead(200);
      res.end(JSON.stringify({ status: "slow-ok" }));
    }, 100);
    return;
  }

  if (url.pathname === "/") {
    res.writeHead(200);
    res.end(JSON.stringify({ service: "webapp-demo", ok: true }));
    return;
  }

  res.writeHead(404);
  res.end(JSON.stringify({ error: "not found", path: url.pathname }));
});

server.listen(PORT, "127.0.0.1", () => {
  console.log(`webapp-demo listening on http://127.0.0.1:${PORT}`);
});
