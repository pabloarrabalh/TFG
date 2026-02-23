export default function LoadingSpinner({ text = 'Cargando...' }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 gap-4">
      <div className="w-10 h-10 rounded-full border-2 border-border-dark border-t-primary animate-spin" />
      {text && <p className="text-gray-400 text-sm">{text}</p>}
    </div>
  )
}
