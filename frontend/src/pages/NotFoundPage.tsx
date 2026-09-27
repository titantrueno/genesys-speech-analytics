import { Link } from 'react-router'

export function NotFoundPage() {
  return (
    <section className="mx-auto mt-16 max-w-md text-center">
      <h1 className="text-2xl font-semibold">Página no encontrada</h1>
      <Link to="/" className="mt-4 inline-block text-brand-600 hover:underline">Volver al inicio</Link>
    </section>
  )
}
