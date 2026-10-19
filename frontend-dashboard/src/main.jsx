import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import AdvertisingConsent from './components/AdvertisingConsent.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
    <AdvertisingConsent />
  </StrictMode>,
)
