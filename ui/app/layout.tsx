import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import { Toaster } from 'sonner'

const inter = Inter({ subsets: ['latin'], variable: '--font-inter' })

export const metadata: Metadata = {
  title: 'PolyTrade v7 | Advanced Polymarket Trading',
  description: 'Production-grade prediction market trading with AI-powered execution'
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.variable} font-sans bg-gray-950 text-gray-100 antialiased`}>
        {children}
        <Toaster position="top-right" theme="dark" closeButton richColors />
      </body>
    </html>
  )
}
