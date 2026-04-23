import './globals.css'
import { Inter } from 'next/font/google'
import Link from 'next/link'

const inter = Inter({ subsets: ['latin'] })

export const metadata = {
  title: 'SENTINEL PREDATOR | Institutional Terminal',
  description: 'Plateforme de surveillance institutionnelle Or (XAU/USD) - Alpha Aboubacar Ambity',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="fr" className="dark">
      <body className={`${inter.className} bg-[#0d1117] text-[#e2e8f0]`}>
        {/* Bottom Tab Bar – Mobile style */}
        <div className="fixed bottom-0 left-0 right-0 z-50 bg-[#161b22] border-t border-[#30363d] flex md:hidden">
          <Link href="/" className="flex-1 flex flex-col items-center py-2 gap-0.5 text-cyan-400 hover:text-cyan-300 transition-colors">
            <span className="text-lg">📊</span>
            <span className="text-[9px] font-black uppercase tracking-wider">Dashboard</span>
          </Link>
          <Link href="/terminal" className="flex-1 flex flex-col items-center py-2 gap-0.5 text-[#8b949e] hover:text-white transition-colors">
            <span className="text-lg">💻</span>
            <span className="text-[9px] font-black uppercase tracking-wider">Terminal</span>
          </Link>
          <Link href="/intelligence" className="flex-1 flex flex-col items-center py-2 gap-0.5 text-[#8b949e] hover:text-white transition-colors">
            <span className="text-lg">🧠</span>
            <span className="text-[9px] font-black uppercase tracking-wider">Intel</span>
          </Link>
          <Link href="/trade" className="flex-1 flex flex-col items-center py-2 gap-0.5 text-[#8b949e] hover:text-white transition-colors">
            <span className="text-lg">⚡</span>
            <span className="text-[9px] font-black uppercase tracking-wider">Trade</span>
          </Link>
          <Link href="/settings" className="flex-1 flex flex-col items-center py-2 gap-0.5 text-[#8b949e] hover:text-white transition-colors">
            <span className="text-lg">⚙️</span>
            <span className="text-[9px] font-black uppercase tracking-wider">Réglages</span>
          </Link>
        </div>

        {/* Top Sidebar Navigation – Desktop */}
        <div className="hidden md:flex fixed top-0 left-0 bottom-0 w-24 bg-[#1b1c23] border-r border-[#2a2c35] flex-col items-center py-6 z-50">
          
          <div className="flex flex-col items-center mb-8">
            {/* SP Shield Logo Mock */}
            <div className="w-10 h-10 flex items-center justify-center relative mb-4">
               <div className="absolute inset-0 border-[2px] border-[#d4a350] rounded bg-[#d4a350]/10 flex items-center justify-center" style={{ clipPath: 'polygon(50% 0%, 100% 25%, 100% 75%, 50% 100%, 0% 75%, 0% 25%)'}}>
                  <span className="text-[#d4a350] font-black text-sm">SP</span>
               </div>
            </div>
            {/* The text logo in sidebar is tricky if it's 24px wide, we'll keep the shield and let the top header handle the textual TITLE or expand the sidebar width. The image has a sidebar of about 80px width, and the "SENTINEL" text is actually positioned to the RIGHT of the sidebar, at the top of the main container. Let's keep the sidebar thin. */}
          </div>

          <div className="flex flex-col w-full gap-2">
            {[
              { href: '/', icon: '◫', label: 'Dashboard', active: true },
              { href: '/terminal', icon: '⌨', label: 'Terminal', active: false },
              { href: '/intelligence', icon: '💡', label: 'Intel', active: false },
              { href: '/trade', icon: '↗', label: 'Trade', active: false },
              { href: '/settings', icon: '⚙', label: 'Config', active: false },
            ].map(item => (
              <Link key={item.href} href={item.href} className={`flex flex-col w-full items-center gap-1.5 py-4 transition-colors relative ${item.active ? 'text-[#d4a350] bg-[#d4a350]/5' : 'text-[#6b7280] hover:text-white'}`}>
                {item.active && <div className="absolute left-0 top-0 bottom-0 w-1 bg-[#d4a350]" />}
                <span className="text-xl">{item.icon}</span>
                <span className="text-[10px] font-medium tracking-wide">{item.label}</span>
              </Link>
            ))}
          </div>
        </div>

        {/* Top Floating Header Element (Integrated at the Layout level to stay constant or we can do it on page.tsx, let's leave it for page.ts for data) */}
        
        {/* Main Content */}
        <div className="md:ml-24 pb-16 md:pb-0 min-h-screen bg-[#111216]">
          {children}
        </div>
      </body>
    </html>
  )
}
