export default function GlassPanel({ children, className = '', ...props }) {
  return (
    <div className={`glass-panel ${className}`} {...props}>
      {children}
    </div>
  )
}
