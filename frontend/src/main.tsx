import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import '@fortawesome/fontawesome-free/css/all.min.css'
import './index.css'
import App from './App.tsx'
import { NoModelError } from './components/NoModelError.tsx'
import { LoginLoading } from './components/LoginLoading.tsx'
import { LoginSuccess } from './components/LoginSuccess.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<App />} />
        <Route path="/no-model" element={<NoModelError />} />
        <Route path="/login-loading" element={<LoginLoading />} />
        <Route path="/login-success" element={<LoginSuccess />} />
      </Routes>
    </BrowserRouter>
  </StrictMode>,
)
