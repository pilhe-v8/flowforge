import React from 'react'
import ReactDOM from 'react-dom/client'
import { Toaster } from 'sonner'
import { ErrorBoundary } from './components/shared/ErrorBoundary'
import { DevAuthBootstrap } from './components/DevAuthBootstrap'
import { AppRouterProvider } from './router'
import './styles/index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <Toaster position="top-right" richColors />
      <DevAuthBootstrap />
      <AppRouterProvider />
    </ErrorBoundary>
  </React.StrictMode>
)
