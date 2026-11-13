import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import AdvertisingConsent from './components/AdvertisingConsent.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
    {/^\/mei\/?$/.test(window.location.pathname) && (
      <footer className="solveris-mei-legal-footer">
        SOLVERIS é uma ferramenta de apoio e orientação; não substitui obrigações fiscais oficiais nem garante regularidade.
      </footer>
    )}
    <AdvertisingConsent />
  </StrictMode>,
)
