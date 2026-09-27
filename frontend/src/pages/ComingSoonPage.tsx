import { Sparkles } from 'lucide-react'
import type { NavItem } from '../layout/navigation'

export function ComingSoonPage({ item }: { item: NavItem }) {
  const Icon = item.icon
  return (
    <section>
      <h1 className="text-2xl font-semibold text-slate-900">{item.label}</h1>
      <div className="mt-8 flex flex-col items-center rounded-xl border border-dashed border-slate-300 bg-white px-6 py-16 text-center">
        <Icon className="size-10 text-brand-500" aria-hidden />
        <p className="mt-4 inline-flex items-center gap-1.5 rounded-full bg-brand-50 px-3 py-1 text-sm font-medium text-brand-700">
          <Sparkles className="size-4" aria-hidden />
          Próximamente
        </p>
        <p className="mt-3 max-w-md text-slate-600">{item.description}</p>
      </div>
    </section>
  )
}
