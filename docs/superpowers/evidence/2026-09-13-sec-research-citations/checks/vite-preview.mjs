import { defineConfig } from '../../../node_modules/vite/dist/node/index.js';
import react from '../../../node_modules/@vitejs/plugin-react/dist/index.js';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../../../', import.meta.url));
export default defineConfig({
  root: fileURLToPath(new URL('./browser-fixture', import.meta.url)),
  cacheDir: fileURLToPath(new URL('./vite-cache', import.meta.url)),
  plugins: [react()],
  resolve: { alias: { '@product': root + 'apps/arkscope-web/src' } },
  server: { host: '127.0.0.1', port: 8457, strictPort: true,
    fs: { allow: [root] } },
});
