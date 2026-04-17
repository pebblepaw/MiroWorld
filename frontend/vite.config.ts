import react from '@vitejs/plugin-react-swc';
import path from 'path';
import {defineConfig, loadEnv} from 'vite';
import { resolveHostedViteDefine } from './src/lib/hosted-env';

export default defineConfig(({mode}) => {
  const env = {
    ...process.env,
    ...loadEnv(mode, '.', ''),
  };

  return {
    base: env.VITE_PUBLIC_BASE || '/',
    plugins: [react()],
    define: resolveHostedViteDefine(env),
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: {
      hmr: process.env.DISABLE_HMR !== 'true',
    },
  };
});
