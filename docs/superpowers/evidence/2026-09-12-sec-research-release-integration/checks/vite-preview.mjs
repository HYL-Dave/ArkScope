import { defineConfig } from '../../../node_modules/vite/dist/node/index.js';
import react from '../../../node_modules/@vitejs/plugin-react/dist/index.js';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../../../', import.meta.url));
export default defineConfig({
  root: fileURLToPath(new URL('./browser-fixture', import.meta.url)),
  cacheDir: process.env.ARKSCOPE_OFFLINE_TEST_WORKSPACE + '/vite-cache',
  plugins: [react()],
  resolve: { alias: { '@product': root + 'apps/arkscope-web/src' } },
  server: { host: '127.0.0.1', port: Number(process.env.FIXTURE_VITE_PORT), strictPort: true,
    proxy: { '/api': { target: process.env.FIXTURE_API, rewrite: path => path.slice(4) } },
    fs: { allow: [root] } },
});
