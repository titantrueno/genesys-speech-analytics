import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { AppProviders } from './App'
import { createAppRouter } from './router'
import './index.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AppProviders router={createAppRouter()} />
  </StrictMode>,
)
