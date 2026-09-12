import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import { mkdirSync, writeFileSync } from 'node:fs';
import net from 'node:net';
import dns from 'node:dns';
import dgram from 'node:dgram';

const work = dirname(fileURLToPath(import.meta.url));
const root = resolve(work, '../../..');
const reject = () => { throw new Error('Fixture server cannot initiate network connections'); };
net.Socket.prototype.connect = reject;
const lookup = dns.lookup;
dns.lookup = (host, ...args) => host === '127.0.0.1' ? lookup(host, ...args) : reject();
dns.resolve = reject;
dgram.Socket.prototype.send = reject;
const requireWeb = createRequire(resolve(root, 'apps/arkscope-web/package.json'));
const { createServer } = await import('vite');
const react = (await import('@vitejs/plugin-react')).default;
mkdirSync(resolve(work, 'task1-server-home'), { recursive: true });
const server = await createServer({
  root: resolve(work, 'task1-fixture'), configFile: false, envFile: false,
  publicDir: false, cacheDir: resolve(work, 'task1-vite-cache'),
  plugins: [react()], resolve: { alias: { '@product': resolve(root, 'apps/arkscope-web/src') } },
  server: { host: '127.0.0.1', port: 8457, strictPort: true, hmr: false,
    watch: { ignored: ['**/.git/**', '**/data/**', '**/config/**'] },
    fs: { strict: true, allow: [resolve(work, 'task1-fixture'), resolve(work, 'task1-vite-cache'),
      resolve(root, 'apps/arkscope-web/src'), dirname(requireWeb.resolve('react/package.json')) + '/..'] } },
});
const receipt = { pid: process.pid, startedAt: new Date().toISOString(), closed: false,
  fixtureOnly: true, envFile: false, appImported: false, networkInitiation: 'blocked' };
const save = () => writeFileSync(resolve(work, 'task1-server.json'), JSON.stringify(receipt, null, 2) + '\n');
let closing = false;
async function close() {
  if (closing) return;
  closing = true;
  await server.close();
  receipt.closed = true;
  receipt.closedAt = new Date().toISOString();
  save();
}
process.on('SIGINT', () => void close());
process.on('SIGTERM', () => void close());
try {
  await server.listen();
  receipt.url = server.resolvedUrls.local[0];
  save();
  console.log(JSON.stringify(receipt));
} catch (error) {
  await close();
  throw error;
}
