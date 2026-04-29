'use client'

import { createContext, useContext, useEffect, useRef, useState, ReactNode } from 'react'

interface WebSocketContextType {
  connected: boolean
  lastMessage: any
  sendMessage: (message: any) => void
}

const WebSocketContext = createContext<WebSocketContextType>({
  connected: false,
  lastMessage: null,
  sendMessage: () => {}
})

export function WebSocketProvider({ children }: { children: ReactNode }) {
  const [connected, setConnected] = useState(false)
  const [lastMessage, setLastMessage] = useState<any>(null)
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    const wsUrl = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000/ws'
    const ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      setConnected(true)
      ws.send(JSON.stringify({ type: 'subscribe', channels: ['trades', 'signals'] }))
    }

    ws.onmessage = (event) => setLastMessage(JSON.parse(event.data))
    ws.onclose = () => setConnected(false)
    ws.onerror = (error) => console.error('WebSocket error:', error)

    wsRef.current = ws
    return () => ws.close()
  }, [])

  const sendMessage = (message: any) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message))
    }
  }

  return (
    <WebSocketContext.Provider value={{ connected, lastMessage, sendMessage }}>
      {children}
    </WebSocketContext.Provider>
  )
}

export const useWebSocket = () => useContext(WebSocketContext)
