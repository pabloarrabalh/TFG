import { Routes, Route, Navigate } from 'react-router-dom'
import { lazy, Suspense } from 'react'
import { AuthProvider, useAuth } from './context/AuthContext'
import { JornadaProvider } from './context/JornadaContext'
import { TourProvider } from './context/TourContext'
import Layout from './components/layout/Layout'
import LoadingSpinner from './components/ui/LoadingSpinner'

// Pages (lazy-loaded)

const LoginPage         = lazy(() => import('./pages/LoginPage'))
const MenuPage          = lazy(() => import('./pages/MenuPage'))
const ClasificacionPage = lazy(() => import('./pages/ClasificacionPage'))
const EquiposPage       = lazy(() => import('./pages/EquiposPage'))
const EquipoPage        = lazy(() => import('./pages/EquipoPage'))
const JugadorPage       = lazy(() => import('./pages/JugadorPage'))
const EstadisticasPage  = lazy(() => import('./pages/EstadisticasPage'))
const MiPlantillaPage   = lazy(() => import('./pages/MiPlantillaPage'))
const PerfilPage        = lazy(() => import('./pages/PerfilPage'))
const AmigosPage        = lazy(() => import('./pages/AmigosPage'))
const AmigoPlantillaPage = lazy(() => import('./pages/AmigoPlantillaPage'))
const SelectFavoritesPage = lazy(() => import('./pages/SelectFavoritesPage'))
const TermsPage         = lazy(() => import('./pages/TermsPage'))

function ProtectedRoute({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <LoadingSpinner />
  if (!user) return <Navigate to="/login" replace />
  return children
}

function AppRoutes() {
  return (
    <Suspense fallback={<div className="flex items-center justify-center h-screen bg-background-dark"><LoadingSpinner /></div>}>
      <Routes>
        {/* Public routes (no layout) */}
        <Route path="/login" element={<LoginPage />} />
        <Route path="/terms" element={<TermsPage />} />

        {/* Routes with layout */}
        <Route path="/" element={<Layout><Navigate to="/menu" replace /></Layout>} />
        <Route path="/menu" element={<Layout><MenuPage /></Layout>} />
        <Route path="/clasificacion" element={<Layout><ClasificacionPage /></Layout>} />
        <Route path="/equipos" element={<Layout><EquiposPage /></Layout>} />
        <Route path="/equipo/:nombre" element={<Layout><EquipoPage /></Layout>} />
        <Route path="/jugador" element={<Layout><JugadorPage /></Layout>} />
        <Route path="/jugador/:id" element={<Layout><JugadorPage /></Layout>} />
        <Route path="/estadisticas" element={<Layout><EstadisticasPage /></Layout>} />

        {/* Protected routes */}
        <Route path="/mi-plantilla" element={
          <Layout><ProtectedRoute><MiPlantillaPage /></ProtectedRoute></Layout>
        } />
        <Route path="/perfil" element={
          <Layout><ProtectedRoute><PerfilPage /></ProtectedRoute></Layout>
        } />
        <Route path="/amigos" element={
          <Layout><ProtectedRoute><AmigosPage /></ProtectedRoute></Layout>
        } />
        <Route path="/amigos/:userId/plantilla" element={
          <Layout><ProtectedRoute><AmigoPlantillaPage /></ProtectedRoute></Layout>
        } />
        <Route path="/favoritos/select" element={
          <Layout><ProtectedRoute><SelectFavoritesPage /></ProtectedRoute></Layout>
        } />

        {/* Fallback */}
        <Route path="*" element={<Navigate to="/menu" replace />} />
      </Routes>
    </Suspense>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <JornadaProvider>
        <TourProvider>
          <AppRoutes />
        </TourProvider>
      </JornadaProvider>
    </AuthProvider>
  )
}
