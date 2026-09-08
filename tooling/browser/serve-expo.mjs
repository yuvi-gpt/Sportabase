import http from 'node:http';
import { access, readFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(fileURLToPath(new URL('../../mobile/dist/', import.meta.url)));
const types = { '.css': 'text/css; charset=utf-8', '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.json': 'application/json; charset=utf-8', '.mjs': 'text/javascript; charset=utf-8', '.png': 'image/png', '.svg': 'image/svg+xml', '.ttf': 'font/ttf', '.woff': 'font/woff', '.woff2': 'font/woff2' };

async function resolveTarget(pathname) {
  const requested = pathname === '/' ? '/index.html' : pathname;
  const candidates = [requested, path.extname(requested) ? '' : `${requested}.html`].filter(Boolean);
  for (const candidate of candidates) {
    const target = path.resolve(root, `.${candidate}`);
    if (target !== root && !target.startsWith(`${root}${path.sep}`)) continue;
    try { await access(target); return target; } catch { /* Try the route export form. */ }
  }
  return null;
}

export function createExpoStaticServer() {
  return http.createServer(async (request, response) => {
    try {
      const pathname = decodeURIComponent(new URL(request.url, 'http://localhost').pathname);
      if (pathname.includes('..')) { response.writeHead(403).end(); return; }
      const target = await resolveTarget(pathname);
      if (!target) { response.writeHead(404).end('Not found'); return; }
      response.setHeader('Content-Type', types[path.extname(target)] || 'application/octet-stream');
      response.setHeader('Cache-Control', 'no-store'); response.end(await readFile(target));
    } catch { response.writeHead(404).end('Not found'); }
  });
}

export async function startExpoServer(port = 4174) {
  const server = createExpoStaticServer();
  await new Promise((resolve, reject) => { server.once('error', reject); server.listen(port, '127.0.0.1', resolve); });
  return server;
}
export async function stopExpoServer(server) { server.closeAllConnections?.(); await new Promise((resolve) => server.close(resolve)); }

if (process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1])) {
  const server = await startExpoServer();
  const shutdown = () => void stopExpoServer(server).then(() => process.exit(0));
  process.once('SIGINT', shutdown); process.once('SIGTERM', shutdown);
}
