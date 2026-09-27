import { ShieldAlert } from 'lucide-react'

export function ForbiddenPage() {
  return (
    <section className="mx-auto mt-16 max-w-md text-center">
      <ShieldAlert className="mx-auto size-10 text-amber-500" aria-hidden />
      <h1 className="mt-4 text-2xl font-semibold">Sin acceso</h1>
      <p className="mt-2 text-slate-600">Tu rol no tiene permiso para ver esta sección. Si lo necesitas, pídeselo a un administrador.</p>
    </section>
  )
}
