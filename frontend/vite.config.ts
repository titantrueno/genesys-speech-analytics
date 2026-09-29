import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': process.env.API_PROXY_TARGET ?? 'http://localhost:8000',
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    // Las fechas con hora se muestran en la zona del navegador; los tests fijan UTC para ser deterministas.
    env: { TZ: 'UTC' },
    // Con la máquina cargada, los tests con debounce del explorador pasan de 5 s (el valor por defecto) sin estar
    // colgados: el límite solo corta tests bloqueados, no alarga los que pasan.
    testTimeout: 15_000,
  },
})
