import {defineConfig} from '../../../node_modules/vite/dist/node/index.js';
import react from '../../../node_modules/@vitejs/plugin-react/dist/index.js';
import {fileURLToPath} from 'node:url';
const root = fileURLToPath(new URL('../../../apps/arkscope-web', import.meta.url));
const cacheDir = fileURLToPath(new URL('./vite-cache', import.meta.url));
export default defineConfig({
  root, cacheDir, plugins: [react()],
  optimizeDeps: {include: ['react', 'react-dom/client', 'i18next']},
  server: {host: '127.0.0.1', port: 8457, strictPort: true,
    fs: {allow: [fileURLToPath(new URL('../../../', import.meta.url)),
                '/mnt/md0/PycharmProjects/ArkScope/node_modules']}},
});
