import { Link, useNavigate } from 'react-router-dom'

const SECTIONS = [
  {
    title: 'Bienvenido a LigaMaster',
    content: 'Estos términos y condiciones rigen el acceso y uso de LigaMaster, una plataforma de fantasía basada en la Liga de Fútbol Profesional. Al registrarte y usar nuestros servicios, aceptas completamente estos términos.',
  },
  {
    title: '1. Definiciones',
    items: [
      { label: 'Plataforma', desc: 'El sitio web y aplicación de LigaMaster' },
      { label: 'Usuario', desc: 'Cualquier persona que acceda o use la Plataforma' },
      { label: 'Contenido', desc: 'Todo material, datos y información disponibles en LigaMaster' },
      { label: 'Servicios', desc: 'Las funcionalidades ofrecidas por LigaMaster' },
    ],
  },
  {
    title: '2. Aceptación de Términos',
    content: 'Al registrarte y crear una cuenta en LigaMaster, confirmas que:',
    items: [
      'Tienes al menos 18 años de edad',
      'Posees autoridad legal para celebrar estos términos',
      'Aceptas todos los términos y condiciones aquí establecidos',
      'Te comprometes a usar la Plataforma de conformidad con la ley',
    ],
  },
  {
    title: '3. Licencia de Uso',
    content: 'LigaMaster te otorga una licencia limitada, no exclusiva y revocable para acceder y usar la Plataforma únicamente para fines personales y no comerciales. Puedes:',
    items: ['Ver y acceder al Contenido', 'Crear tu equipo de fantasía', 'Participar en competiciones'],
    footer: 'No puedes reproducir, distribuir, modificar o transmitir el Contenido sin permiso previo.',
  },
  {
    title: '4. Registro de Cuenta',
    content: 'Al registrarte, eres responsable de mantener la confidencialidad de tu contraseña y de toda actividad que ocurra bajo tu cuenta. Debes:',
    items: [
      'Proporcionar información exacta y veraz',
      'Notificarnos inmediatamente de accesos no autorizados',
      'No compartir tu contraseña con terceros',
    ],
  },
  {
    title: '5. Conducta del Usuario',
    content: 'Se prohíbe estrictamente:',
    items: [
      'Acceso no autorizado a sistemas o datos',
      'Interferencia con la operación de la Plataforma',
      'Conducta abusiva o acosadora hacia otros usuarios',
      'Distribución de malware o código malicioso',
      'Violación de derechos de propiedad intelectual',
    ],
  },
  {
    title: '6. Propiedad Intelectual',
    content: 'Todo el Contenido en LigaMaster, incluyendo pero no limitado a texto, gráficos, logos y software, es propiedad de LigaMaster o sus proveedores de contenido y está protegido por leyes de derechos de autor.',
  },
  {
    title: '7. Limitación de Responsabilidad',
    content: 'LA PLATAFORMA SE PROPORCIONA "TAL COMO ESTÁ" SIN GARANTÍAS DE NINGÚN TIPO. NO SOMOS RESPONSABLES POR:',
    items: [
      'Interrupciones o fallas del servicio',
      'Pérdida de datos',
      'Errores o inexactitudes en la información',
      'Daños indirectos o consecuentes',
    ],
  },
  {
    title: '8. Modificaciones de los Términos',
    content: 'LigaMaster se reserva el derecho de modificar estos términos en cualquier momento. Las modificaciones entrarán en vigencia una vez publicadas. Tu uso continuado de la Plataforma constituye aceptación de los términos modificados.',
  },
  {
    title: '9. Cancelación',
    content: 'Podemos cancelar o suspender tu cuenta en cualquier momento, por cualquier razón, incluyendo violación de estos términos.',
  },
  {
    title: '10. Ley Aplicable',
    content: 'Estos términos se rigen por la legislación vigente en España. Cualquier disputa se resolverá ante los tribunales competentes de España.',
  },
  {
    title: '11. Contacto',
    content: 'Si tienes preguntas sobre estos términos o la Plataforma, puedes contactarnos a través de nuestro sitio web.',
  },
]

export default function TermsPage() {
  const navigate = useNavigate()

  return (
    <div className="min-h-screen bg-background-dark text-white py-12 px-6">
      <div className="max-w-3xl mx-auto">
        {/* Header */}
        <div className="mb-12">
          <h1 className="text-4xl md:text-5xl font-black text-white mb-4">Términos y Condiciones</h1>
          <p className="text-gray-400">Última actualización: 11 de Febrero de 2026</p>
        </div>

        {/* Content sections */}
        <div className="space-y-8 text-gray-300 leading-relaxed">
          {SECTIONS.map((sec, i) => (
            <section key={i}>
              <h2 className="text-2xl font-bold text-white mb-3">{sec.title}</h2>
              {sec.content && <p className="mb-3">{sec.content}</p>}
              {sec.items && (
                <ul className="space-y-2 ml-4 list-disc mt-3">
                  {sec.items.map((item, j) =>
                    typeof item === 'string' ? (
                      <li key={j}>{item}</li>
                    ) : (
                      <li key={j}><strong>{item.label}:</strong> {item.desc}</li>
                    )
                  )}
                </ul>
              )}
              {sec.footer && <p className="mt-3">{sec.footer}</p>}
            </section>
          ))}
        </div>

        {/* Back button */}
        <div className="mt-12 pt-8 border-t border-border-dark">
          <button
            onClick={() => navigate('/login')}
            className="inline-flex items-center gap-2 px-6 py-3 bg-primary text-black font-bold rounded-xl hover:bg-primary-dark transition-colors"
          >
            <span className="material-symbols-outlined">arrow_back</span>
            Volver al Login
          </button>
        </div>
      </div>
    </div>
  )
}
