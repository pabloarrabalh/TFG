import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function LoginPage() {
  const { login, register } = useAuth()
  const navigate = useNavigate()
  const [tab, setTab] = useState('login')

  // Login state
  const [loginData, setLoginData] = useState({ username: '', password: '' })
  const [loginError, setLoginError] = useState('')
  const [loginLoading, setLoginLoading] = useState(false)
  const [showLoginPwd, setShowLoginPwd] = useState(false)

  // Register state
  const [regData, setRegData] = useState({
    first_name: '',
    last_name: '',
    email: '',
    username: '',
    password1: '',
    password2: '',
  })
  const [regErrors, setRegErrors] = useState({})
  const [regLoading, setRegLoading] = useState(false)
  const [showRegPwd, setShowRegPwd] = useState(false)

  const handleLoginSubmit = async (e) => {
    e.preventDefault()
    setLoginLoading(true)
    setLoginError('')
    try {
      await login(loginData.username, loginData.password)
      navigate('/menu')
    } catch (err) {
      setLoginError(err?.response?.data?.error || 'Credenciales incorrectas')
    } finally {
      setLoginLoading(false)
    }
  }

  const handleRegisterSubmit = async (e) => {
    e.preventDefault()
    setRegLoading(true)
    setRegErrors({})
    try {
      await register(regData)
      // Limpiar flags del tour para mostrar modal de bienvenida a nuevo usuario
      localStorage.removeItem('_tour_offered')
      localStorage.removeItem('_tour_active')
      localStorage.removeItem('_tour_done')
      navigate('/favoritos/select')
    } catch (err) {
      setRegErrors(err?.response?.data?.errors || { general: 'Error al registrarse' })
    } finally {
      setRegLoading(false)
    }
  }

  return (
    <div className="flex h-screen w-full bg-background-dark font-display">
      {/* Left hero panel (desktop) */}
      <div className="relative hidden lg:flex w-1/2 flex-col justify-end p-12 h-full overflow-hidden">
        <div
          className="absolute inset-0 bg-cover bg-center scale-105 transition-opacity duration-1000"
          style={{
            backgroundImage: `url('https://lh3.googleusercontent.com/aida-public/AB6AXuBzeXpYJkPHG_3uYl9-UJnVZUYz_QbYbmmql3pS_oo5mv03eJI7MV-UWEAOkGEm1lQ8Ki4Ky-uNhHIs7660_2BBTrm4noHBp2hcSYTMoP8xWuk3ea-rn8NYwhvv_tXv9HPvComYVXhKJTOfCbAeFw_m_SfYK9wOufTo7013cbt8_8GlrTUZgzrRs0YwikgdQi77uUcJj75uVGasvma-M5zgKbxb2_e--KFWgkiQmn18dLr-mvC930WNGB4_VHwUMUv0bXl1GlZogD0')`,
            filter: 'brightness(0.6) contrast(1.1)',
          }}
        />
        <div className="absolute inset-0 bg-gradient-to-t from-background-dark via-black/50 to-black/30 opacity-90" />
        <div className="relative z-10 flex flex-col max-w-lg">
          <div className="mb-4 flex items-center gap-3">
            <span className="material-symbols-outlined text-4xl text-primary drop-shadow-[0_0_5px_rgba(57,255,20,0.8)]">sports_soccer</span>
            <h1 className="text-3xl font-black tracking-tight text-white">LigaMaster</h1>
          </div>
          <h2 className="text-4xl font-bold leading-tight tracking-tight text-white mb-4">
            Gestiona tu equipo soñado como un profesional.
          </h2>
          <p className="text-base text-gray-300 font-light mb-8">
            Únete a más de 5 millones de entrenadores compitiendo en la liga oficial de fantasía de LaLiga. Crea tu plantilla, sigue estadísticas en vivo y domina la clasificación.
          </p>
          <div className="flex items-center gap-4">
            <div className="flex -space-x-4">
              <div className="flex items-center justify-center w-10 h-10 text-xs font-bold text-black bg-primary rounded-full border-2 border-background-dark shadow-neon cursor-pointer">+2k</div>
            </div>
            <div className="text-sm font-medium text-gray-300">Managers activos online</div>
          </div>
        </div>
      </div>

      {/* Right: auth forms */}
      <div className="flex w-full lg:w-1/2 flex-col items-center justify-start bg-background-dark px-4 py-8 sm:px-12 h-full overflow-y-auto border-l border-border-dark pb-32">
        {/* Mobile brand */}
        <div className="lg:hidden mb-8 flex items-center gap-2">
          <span className="material-symbols-outlined text-3xl text-primary">sports_soccer</span>
          <span className="text-2xl font-black tracking-tight text-white">LigaMaster</span>
        </div>

        <div className="w-full max-w-[440px] flex flex-col gap-6">
          <div className="rounded-2xl bg-surface-dark-lighter p-8 shadow-2xl border border-primary/20 hover:border-primary/40 transition-colors relative overflow-hidden group">
            <div className="absolute -top-20 -right-20 w-40 h-40 bg-primary/5 blur-[80px] rounded-full pointer-events-none group-hover:bg-primary/10 transition-colors" />

            <div className="mb-6 text-center">
              <h2 className="text-2xl font-bold text-white">
                {tab === 'login' ? 'Bienvenido de nuevo' : 'Crea tu cuenta'}
              </h2>
              <p className="mt-2 text-sm text-gray-500">
                {tab === 'login' ? 'Introduce tus datos para acceder' : 'Únete a LigaMaster gratis'}
              </p>
            </div>

            {/* Tabs */}
            <div className="mb-8 flex w-full border-b border-border-dark">
              {['login', 'register'].map((t) => (
                <button
                  key={t}
                  onClick={() => setTab(t)}
                  className={`relative flex flex-1 items-center justify-center pb-3 text-sm font-bold tracking-wide transition-colors ${
                    tab === t ? 'text-primary' : 'text-gray-500 hover:text-white'
                  }`}
                >
                  {t === 'login' ? 'Inicia sesión' : 'Regístrate'}
                  {tab === t && (
                    <span className="absolute bottom-0 left-0 h-0.5 w-full bg-primary shadow-[0_0_8px_#39ff14]" />
                  )}
                </button>
              ))}
            </div>

            {/* LOGIN FORM */}
            {tab === 'login' && (
              <form onSubmit={handleLoginSubmit} className="flex flex-col gap-5">
                <div className="flex flex-col gap-2">
                  <label className="text-sm font-medium text-gray-300">Correo electrónico / Usuario</label>
                  <div className="relative flex items-center group/input">
                    <span className="material-symbols-outlined absolute left-4 text-gray-500 group-focus-within/input:text-primary transition-colors select-none text-[20px]">mail</span>
                    <input
                      type="text"
                      placeholder="manager@ejemplo.com"
                      required
                      value={loginData.username}
                      onChange={(e) => setLoginData({ ...loginData, username: e.target.value })}
                      className="w-full rounded-lg border border-border-dark bg-background-dark px-4 py-3 pl-11 text-sm text-white placeholder-gray-600 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary transition-all"
                    />
                  </div>
                </div>

                <div className="flex flex-col gap-2">
                  <div className="flex items-center justify-between">
                    <label className="text-sm font-medium text-gray-300">Contraseña</label>
                    <a href="#" className="text-xs font-semibold text-primary hover:text-primary/80 transition-colors">¿Olvidaste la contraseña?</a>
                  </div>
                  <div className="relative flex items-center group/input">
                    <span className="material-symbols-outlined absolute left-4 text-gray-500 group-focus-within/input:text-primary transition-colors select-none text-[20px]">lock</span>
                    <input
                      type={showLoginPwd ? 'text' : 'password'}
                      placeholder="Introduce tu contraseña"
                      required
                      value={loginData.password}
                      onChange={(e) => setLoginData({ ...loginData, password: e.target.value })}
                      className="w-full rounded-lg border border-border-dark bg-background-dark px-4 py-3 pl-11 pr-11 text-sm text-white placeholder-gray-600 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary transition-all"
                    />
                    <button type="button" onClick={() => setShowLoginPwd((p) => !p)} className="absolute right-4 text-gray-500 hover:text-white transition-colors">
                      <span className="material-symbols-outlined text-[20px]">{showLoginPwd ? 'visibility' : 'visibility_off'}</span>
                    </button>
                  </div>
                </div>

                {loginError && (
                  <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg">
                    <p className="text-red-400 text-sm">{loginError}</p>
                  </div>
                )}

                <button
                  type="submit"
                  disabled={loginLoading}
                  className="mt-2 flex w-full items-center justify-center rounded-lg bg-primary py-3 px-4 text-sm font-black uppercase tracking-wider text-black shadow-neon transition-all hover:bg-primary-dark hover:-translate-y-0.5 active:scale-[0.98] disabled:opacity-60"
                >
                  {loginLoading ? 'Entrando...' : 'Entrar'}
                </button>
              </form>
            )}

            {/* REGISTER FORM */}
            {tab === 'register' && (
              <form onSubmit={handleRegisterSubmit} className="flex flex-col gap-4">
                <div className="flex flex-col gap-2">
                  <label className="text-sm font-medium text-gray-300">Nombre</label>
                  <div className="relative flex items-center group/input">
                    <span className="material-symbols-outlined absolute left-4 text-gray-500 group-focus-within/input:text-primary transition-colors select-none text-[20px]">badge</span>
                    <input
                      type="text" placeholder="Tu nombre" required
                      value={regData.first_name}
                      onChange={(e) => setRegData({ ...regData, first_name: e.target.value })}
                      className="w-full rounded-lg border border-border-dark bg-background-dark px-4 py-3 pl-11 text-sm text-white placeholder-gray-600 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary transition-all"
                    />
                  </div>
                  {regErrors.first_name && <p className="text-red-400 text-xs">{regErrors.first_name}</p>}
                </div>

                <div className="flex flex-col gap-2">
                  <label className="text-sm font-medium text-gray-300">Apellido (opcional)</label>
                  <div className="relative flex items-center group/input">
                    <span className="material-symbols-outlined absolute left-4 text-gray-500 group-focus-within/input:text-primary transition-colors select-none text-[20px]">person</span>
                    <input
                      type="text" placeholder="Tu apellido"
                      value={regData.last_name}
                      onChange={(e) => setRegData({ ...regData, last_name: e.target.value })}
                      className="w-full rounded-lg border border-border-dark bg-background-dark px-4 py-3 pl-11 text-sm text-white placeholder-gray-600 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary transition-all"
                    />
                  </div>
                  {regErrors.last_name && <p className="text-red-400 text-xs">{regErrors.last_name}</p>}
                </div>

                <div className="flex flex-col gap-2">
                  <label className="text-sm font-medium text-gray-300">Email</label>
                  <div className="relative flex items-center group/input">
                    <span className="material-symbols-outlined absolute left-4 text-gray-500 group-focus-within/input:text-primary transition-colors select-none text-[20px]">mail</span>
                    <input
                      type="email" placeholder="manager@ejemplo.com" required
                      value={regData.email}
                      onChange={(e) => setRegData({ ...regData, email: e.target.value })}
                      className="w-full rounded-lg border border-border-dark bg-background-dark px-4 py-3 pl-11 text-sm text-white placeholder-gray-600 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary transition-all"
                    />
                  </div>
                  {regErrors.email && <p className="text-red-400 text-xs">{regErrors.email}</p>}
                </div>

                <div className="flex flex-col gap-2">
                  <label className="text-sm font-medium text-gray-300">Apodo (unico)</label>
                  <div className="relative flex items-center group/input">
                    <span className="material-symbols-outlined absolute left-4 text-gray-500 group-focus-within/input:text-primary transition-colors select-none text-[20px]">alternate_email</span>
                    <input
                      type="text" placeholder="miapodo" required
                      value={regData.username}
                      onChange={(e) => setRegData({ ...regData, username: e.target.value })}
                      className="w-full rounded-lg border border-border-dark bg-background-dark px-4 py-3 pl-11 text-sm text-white placeholder-gray-600 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary transition-all"
                    />
                  </div>
                  {regErrors.username && <p className="text-red-400 text-xs">{regErrors.username}</p>}
                </div>

                <div className="flex flex-col gap-2">
                  <label className="text-sm font-medium text-gray-300">Contraseña</label>
                  <div className="relative flex items-center group/input">
                    <span className="material-symbols-outlined absolute left-4 text-gray-500 group-focus-within/input:text-primary transition-colors select-none text-[20px]">lock</span>
                    <input
                      type={showRegPwd ? 'text' : 'password'} placeholder="Mínimo 8 caracteres" required
                      value={regData.password1}
                      onChange={(e) => setRegData({ ...regData, password1: e.target.value })}
                      className="w-full rounded-lg border border-border-dark bg-background-dark px-4 py-3 pl-11 pr-11 text-sm text-white placeholder-gray-600 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary transition-all"
                    />
                    <button type="button" onClick={() => setShowRegPwd((p) => !p)} className="absolute right-4 text-gray-500 hover:text-white transition-colors">
                      <span className="material-symbols-outlined text-[20px]">{showRegPwd ? 'visibility' : 'visibility_off'}</span>
                    </button>
                  </div>
                  {regErrors.password1 && <p className="text-red-400 text-xs">{regErrors.password1}</p>}
                </div>

                <div className="flex flex-col gap-2">
                  <label className="text-sm font-medium text-gray-300">Repetir contraseña</label>
                  <div className="relative flex items-center group/input">
                    <span className="material-symbols-outlined absolute left-4 text-gray-500 group-focus-within/input:text-primary transition-colors select-none text-[20px]">lock</span>
                    <input
                      type="password" placeholder="Repite la contraseña" required
                      value={regData.password2}
                      onChange={(e) => setRegData({ ...regData, password2: e.target.value })}
                      className="w-full rounded-lg border border-border-dark bg-background-dark px-4 py-3 pl-11 text-sm text-white placeholder-gray-600 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary transition-all"
                    />
                  </div>
                  {regErrors.password2 && <p className="text-red-400 text-xs">{regErrors.password2}</p>}
                </div>

                {regErrors.general && (
                  <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg">
                    <p className="text-red-400 text-sm">{regErrors.general}</p>
                  </div>
                )}

                <button
                  type="submit"
                  disabled={regLoading}
                  className="mt-2 flex w-full items-center justify-center rounded-lg bg-primary py-3 px-4 text-sm font-black uppercase tracking-wider text-black shadow-neon transition-all hover:bg-primary-dark hover:-translate-y-0.5 active:scale-[0.98] disabled:opacity-60"
                >
                  {regLoading ? 'Creando cuenta...' : 'Crear cuenta gratis'}
                </button>

                <p className="text-xs text-center text-gray-500 mt-2">
                  Al registrarte aceptas nuestros{' '}
                  <Link to="/terms" className="text-primary hover:underline">Términos y Condiciones</Link>
                </p>
              </form>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
