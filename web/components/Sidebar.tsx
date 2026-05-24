'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'

const links = [
  { href: '/', label: 'Dashboard', icon: '⊞' },
  { href: '/goals', label: 'Goals', icon: '◎' },
  { href: '/settings', label: 'Settings', icon: '⚙' },
]

export default function Sidebar() {
  const pathname = usePathname()

  return (
    <aside className="fixed left-0 top-0 h-full w-56 bg-[#18181b] border-r border-zinc-800 flex flex-col z-40 hidden md:flex">
      {/* Logo */}
      <div className="px-5 py-5 border-b border-zinc-800">
        <span className="text-lg font-semibold tracking-tight text-zinc-100">
          Learnix
        </span>
        <p className="text-xs text-zinc-500 mt-0.5">Learning tracker</p>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {links.map(link => {
          const active =
            link.href === '/'
              ? pathname === '/'
              : pathname.startsWith(link.href)
          return (
            <Link
              key={link.href}
              href={link.href}
              className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                active
                  ? 'bg-indigo-600 text-white'
                  : 'text-zinc-400 hover:bg-zinc-800 hover:text-zinc-100'
              }`}
            >
              <span className="text-base">{link.icon}</span>
              {link.label}
            </Link>
          )
        })}
      </nav>

      {/* Footer */}
      <div className="px-5 py-4 border-t border-zinc-800">
        <p className="text-xs text-zinc-600">v1.0.0</p>
      </div>
    </aside>
  )
}
