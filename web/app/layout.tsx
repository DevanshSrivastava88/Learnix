import type { Metadata } from 'next'
import './globals.css'
import Sidebar from '@/components/Sidebar'

export const metadata: Metadata = {
  title: 'Learnix',
  description: 'Personal learning tracker',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className="flex min-h-screen bg-[#0f0f11] text-zinc-100">
        <Sidebar />
        <main className="flex-1 overflow-auto md:ml-56">
          {children}
        </main>
      </body>
    </html>
  )
}
