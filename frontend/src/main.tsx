import { createRoot } from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { RecoilRoot } from 'recoil'
import '@fortawesome/fontawesome-free/css/all.min.css'
import '@fontsource/fraunces'
import '@fontsource/geist-mono'

import './index.css'
import App from './App.tsx'
import { Login } from './pages/Login.tsx'
import { AuthCallback } from './pages/AuthCallback.tsx'
import { ConnectTwitter } from './pages/ConnectTwitter.tsx'
import { ResetPassword } from './pages/ResetPassword.tsx'
import { LoginError } from './pages/LoginError.tsx'
import { Pricing } from './pages/Pricing.tsx'
import { BillingSuccess } from './pages/BillingSuccess.tsx'
import { Onboarding } from './pages/Onboarding.tsx'
import { NoModelError } from './components/NoModelError.tsx'
import { LoginLoading } from './components/LoginLoading.tsx'
import { LoginSuccess } from './components/LoginSuccess.tsx'

createRoot(document.getElementById('root')!).render(
  <RecoilRoot>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<App />} />
        <Route path="/login" element={<Login />} />
        <Route path="/onboarding" element={<Onboarding />} />
        <Route path="/login-error" element={<LoginError />} />
        <Route path="/auth/callback" element={<AuthCallback />} />
        <Route path="/connect-twitter" element={<ConnectTwitter />} />
        <Route path="/reset-password" element={<ResetPassword />} />
        <Route path="/pricing" element={<Pricing />} />
        <Route path="/billing/success" element={<BillingSuccess />} />
        <Route path="/no-model" element={<NoModelError />} />
        <Route path="/login-loading" element={<LoginLoading />} />
        <Route path="/login-success" element={<LoginSuccess />} />
      </Routes>
    </BrowserRouter>
  </RecoilRoot>,
)
