'use client'

import { useState } from 'react'
import { motion } from 'framer-motion'
import { Activity, Brain, TrendingUp, Shield, BarChart3 } from 'lucide-react'

export default function DashboardPage() {
  const [systemState] = useState('RUNNING')
  const [connected] = useState(true)
  
  return (
    <div className="min-h-screen bg-gray-950">
      <div className="flex h-screen">
        {/* Sidebar */}
        <aside className="w-64 bg-gray-900 border-r border-gray-800 p-4">
          <div className="mb-8">
            <h1 className="text-xl font-bold">
              <span className="text-green-500">PolyTrade</span> v7
            </h1>
          </div>
          <nav className="space-y-2">
            {[
              { icon: BarChart3, label: 'Dashboard', active: true },
              { icon: Brain, label: 'AI Signals', active: false },
              { icon: TrendingUp, label: 'Trading', active: false },
              { icon: Shield, label: 'Risk Manager', active: false },
              { icon: Activity, label: 'Performance', active: false }
            ].map((item) => (
              <button key={item.label} className={`w-full flex items-center space-x-3 px-3 py-2 rounded-lg text-sm transition-colors ${item.active ? 'bg-green-500/10 text-green-500' : 'text-gray-400 hover:bg-gray-800'}`}>
                <item.icon className="w-4 h-4" />
                <span>{item.label}</span>
              </button>
            ))}
          </nav>
        </aside>

        {/* Main Content */}
        <main className="flex-1 overflow-auto p-6">
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-2xl font-bold">Dashboard</h2>
                <p className="text-gray-400 text-sm mt-1">Real-time trading overview</p>
              </div>
              <div className="flex items-center space-x-3">
                <div className="flex items-center space-x-2 px-3 py-1.5 bg-gray-900 rounded-lg border border-gray-800">
                  <div className={`w-2 h-2 rounded-full ${connected ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`} />
                  <span className="text-sm text-gray-400">{connected ? 'Connected' : 'Disconnected'}</span>
                </div>
                <div className="flex items-center space-x-2 px-3 py-1.5 bg-gray-900 rounded-lg border border-gray-800">
                  <div className="w-2 h-2 rounded-full bg-green-500" />
                  <span className="text-sm text-gray-400">{systemState}</span>
                </div>
              </div>
            </div>

            {/* Stats Grid */}
            <div className="grid grid-cols-4 gap-4">
              {[
                { label: 'Portfolio Value', value: '$128,450', change: '+2.4%', positive: true },
                { label: 'Daily P&L', value: '+$3,240', change: '+2.6%', positive: true },
                { label: 'Win Rate', value: '68.5%', change: '+5.2%', positive: true },
                { label: 'Active Positions', value: '3', change: 'Low Risk', positive: true }
              ].map((stat) => (
                <div key={stat.label} className="bg-gray-900 rounded-xl border border-gray-800 p-4">
                  <div className="text-sm text-gray-400">{stat.label}</div>
                  <div className="text-2xl font-bold mt-1">{stat.value}</div>
                  <div className={`text-xs mt-1 ${stat.positive ? 'text-green-500' : 'text-red-500'}`}>{stat.change}</div>
                </div>
              ))}
            </div>

            {/* Chart Area */}
            <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
              <h3 className="text-lg font-semibold mb-4">Equity Curve</h3>
              <div className="h-80 flex items-center justify-center text-gray-600">
                Chart Component (lightweight-charts)
              </div>
            </div>

            {/* AI Signals & Active Trades */}
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
                <h3 className="text-lg font-semibold mb-4">AI Trading Signals</h3>
                <div className="space-y-3">
                  {[
                    { symbol: 'BTC/USD', action: 'BUY', confidence: 0.85, edge: 0.032 },
                    { symbol: 'ETH/USD', action: 'SELL', confidence: 0.72, edge: 0.018 }
                  ].map((signal, i) => (
                    <div key={i} className="bg-gray-800/50 rounded-lg p-3">
                      <div className="flex justify-between items-center">
                        <span className="font-medium">{signal.symbol}</span>
                        <span className={`px-2 py-0.5 rounded text-xs font-bold ${signal.action === 'BUY' ? 'bg-green-500/20 text-green-500' : 'bg-red-500/20 text-red-500'}`}>{signal.action}</span>
                      </div>
                      <div className="text-xs text-gray-400 mt-1">Confidence: {(signal.confidence*100).toFixed(0)}% | Edge: {(signal.edge*100).toFixed(2)}%</div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
                <h3 className="text-lg font-semibold mb-4">Active Positions</h3>
                <div className="space-y-3">
                  {['BTC/USD LONG', 'ETH/USD SHORT'].map((pos, i) => (
                    <div key={i} className="bg-gray-800/50 rounded-lg p-3 flex justify-between items-center">
                      <span className="font-medium">{pos}</span>
                      <span className="text-green-500">+$450</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </motion.div>
        </main>
      </div>
    </div>
  )
}
