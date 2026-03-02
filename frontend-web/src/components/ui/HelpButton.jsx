import { useState, useRef, useEffect } from 'react'

/**
 * HelpButton — floating "?" button at the bottom-right of the screen.
 * 
 * Usage:
 *   <HelpButton fields={[
 *     { label: 'PTS', description: 'Puntos fantasy acumulados en la temporada.' },
 *     ...
 *   ]} />
 * 
 * Or pass a `sections` prop for grouped fields:
 *   <HelpButton sections={[
 *     { title: 'Ataque', fields: [{ label: 'xG', description: '...' }] },
 *     ...
 *   ]} />
 */
export default function HelpButton({ fields = [], sections = [], title = 'Guía de campos' }) {
  const [open, setOpen] = useState(false)
  const panelRef = useRef(null)

  useEffect(() => {
    if (!open) return
    function handle(e) {
      if (panelRef.current && !panelRef.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', handle)
    return () => document.removeEventListener('mousedown', handle)
  }, [open])

  // Normalise: if flat fields given, wrap in one section
  const allSections = sections.length > 0
    ? sections
    : fields.length > 0
      ? [{ title: null, fields }]
      : []

  return (
    <>
      {/* Floating button */}
      <button
        onClick={() => setOpen(o => !o)}
        className="fixed bottom-6 right-6 z-40 w-12 h-12 rounded-full bg-primary hover:bg-primary/80 text-black font-black text-xl shadow-lg flex items-center justify-center transition-all"
        title="Ayuda – descripción de campos"
        aria-label="Ayuda"
      >
        ?
      </button>

      {/* Modal panel */}
      {open && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
          <div
            ref={panelRef}
            className="bg-[#1a1d23] border border-white/10 rounded-2xl shadow-2xl w-full max-w-lg max-h-[80vh] flex flex-col"
          >
            {/* Header */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-white/10">
              <div className="flex items-center gap-2">
                <span className="text-primary font-black text-lg">?</span>
                <h2 className="text-white font-bold text-base">{title}</h2>
              </div>
              <button
                onClick={() => setOpen(false)}
                className="text-gray-400 hover:text-white transition-colors"
              >
                <span className="material-symbols-outlined">close</span>
              </button>
            </div>

            {/* Content */}
            <div className="overflow-y-auto flex-1 px-5 py-4 space-y-5">
              {allSections.length === 0 ? (
                <p className="text-gray-400 text-sm">Sin contenido de ayuda configurado.</p>
              ) : (
                allSections.map((section, si) => (
                  <div key={si}>
                    {section.title && (
                      <p className="text-xs font-black uppercase tracking-widest text-primary mb-2">{section.title}</p>
                    )}
                    <div className="space-y-2">
                      {section.fields.map((f, fi) => (
                        <div key={fi} className="flex gap-3 items-start">
                          <span className="text-xs font-bold text-white bg-white/10 rounded px-2 py-0.5 min-w-[60px] text-center flex-shrink-0 mt-0.5">
                            {f.label}
                          </span>
                          <p className="text-xs text-gray-400 leading-relaxed">{f.description}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </>
  )
}
