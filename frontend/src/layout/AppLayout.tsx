import { AudioLines, LogOut } from 'lucide-react'
import { NavLink, Outlet } from 'react-router'
import { useAuth } from '../auth/useAuth'
import { DEFAULT_PLATFORM_NAME, usePublicConfig } from '../config/api'
import { setDisplayTimeZone } from '../lib/format'
import { NAV_ITEMS } from './navigation'

export function AppLayout() {
  const { user, can, logout } = useAuth()
  const items = NAV_ITEMS.filter((item) => can(item.permission))
  const { data: settings } = usePublicConfig()
  // Se fija durante el render para que las páginas de este mismo render ya formateen en la zona de la plataforma;
  // la `key` del contenido lo vuelve a montar si la zona cambia (FE005).
  setDisplayTimeZone(settings?.timezone)

  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 flex h-screen w-64 shrink-0 flex-col bg-brand-900 text-slate-100">
        <div className="flex items-center gap-3 px-5 py-5">
          <div className="flex size-9 items-center justify-center rounded-lg bg-brand-500">
            <AudioLines className="size-5" aria-hidden />
          </div>
          <div className="leading-tight">
            <p className="text-sm font-semibold">Banco Horizonte</p>
            <p className="text-xs text-slate-300">{settings?.platform_name ?? DEFAULT_PLATFORM_NAME}</p>
          </div>
        </div>
        <nav aria-label="Principal" className="flex-1 space-y-1 px-3 py-2">
          {items.map(({ path, label, icon: Icon }) => (
            <NavLink
              key={path}
              to={path}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors ${
                  isActive ? 'bg-white/15 font-medium text-white' : 'text-slate-300 hover:bg-white/10 hover:text-white'
                }`
              }
            >
              <Icon className="size-4 shrink-0" aria-hidden />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-white/10 p-4">
          <p className="truncate text-sm font-medium">{user?.name}</p>
          <p className="truncate text-xs text-slate-300">{user?.role_name}</p>
          <button
            type="button"
            onClick={logout}
            className="mt-3 flex w-full items-center justify-center gap-2 rounded-md border border-white/20 px-3 py-1.5 text-sm text-slate-200 hover:bg-white/10"
          >
            <LogOut className="size-4" aria-hidden />
            Cerrar sesión
          </button>
        </div>
      </aside>
      <main className="min-w-0 flex-1 px-8 py-6">
        <Outlet key={settings?.timezone ?? ''} />
      </main>
    </div>
  )
}
