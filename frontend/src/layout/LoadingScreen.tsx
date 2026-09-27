import { Loader2 } from 'lucide-react'

export function LoadingScreen({ label = 'Cargando…' }: { label?: string }) {
  return (
    <div className="flex min-h-[50vh] items-center justify-center gap-2 text-slate-500" role="status">
      <Loader2 className="size-5 animate-spin" aria-hidden />
      <span>{label}</span>
    </div>
  )
}
