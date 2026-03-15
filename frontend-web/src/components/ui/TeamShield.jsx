import { useState } from 'react'

const BACKEND = 'http://localhost:8000'

/**
 * Displays a team shield image with fallback.
 * @param {string} escudo - shield filename key (computed by shield_name on backend)
 * @param {string} nombre - team name (for alt text and fallback)
 * @param {string} className - extra CSS classes
 * @param {string} size - size in pixels for fallback
 */
export default function TeamShield({ escudo, nombre = '', className = 'size-8', size = 32 }) {
  const [imageError, setImageError] = useState(false)

  const src = escudo ? `/static/escudos/${escudo}.png` : null
  const fallbackInitial = (nombre || '?')[0].toUpperCase()

  if (imageError || !src) {
    // Fallback: show team initial in a colored circle
    return (
      <div
        className={`flex items-center justify-center rounded-full bg-gradient-to-br from-primary/30 to-primary/10 border border-primary/40 font-bold text-white text-sm flex-shrink-0 ${className}`}
        title={nombre}
      >
        {fallbackInitial}
      </div>
    )
  }

  return (
    <img
      src={src}
      alt={nombre}
      className={`object-contain flex-shrink-0 ${className}`}
      onError={() => setImageError(true)}
      title={nombre}
    />
  )
}
