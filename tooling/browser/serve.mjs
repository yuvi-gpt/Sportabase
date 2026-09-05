import http from "node:http";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
const root = fileURLToPath(new URL("../../frontend/", import.meta.url));
const types = {".html":"text/html", ".mjs":"text/javascript", ".css":"text/css", ".json":"application/json", ".js":"text/javascript"};
export function createStaticServer() { return http.createServer(async (req, res) => {
  try {
    const pathname = decodeURIComponent(new URL(req.url, "http://localhost").pathname);
    const target = path.resolve(root, "." + (pathname === "/" ? "/index.html" : pathname));
    if (!target.startsWith(root) || pathname.includes("..")) { res.writeHead(403).end(); return; }
    res.setHeader("Content-Type", types[path.extname(target)] || "application/octet-stream");
    res.setHeader("Cache-Control", "no-store"); res.end(await readFile(target));
  } catch { res.writeHead(404).end(); }
}); }

export async function startServer(port = 4173) {
  const server = createStaticServer();
  await new Promise((resolve, reject) => { server.once("error", reject); server.listen(port, "127.0.0.1", resolve); });
  return server;
}

export async function stopServer(server) {
  server.closeAllConnections?.();
  await new Promise(resolve => server.close(resolve));
}

if (process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1])) {
  const server = await startServer();
  function shutdown() {
    void stopServer(server).then(() => process.exit(0));
  }
  process.once("SIGINT", shutdown);
  process.once("SIGTERM", shutdown);
}
