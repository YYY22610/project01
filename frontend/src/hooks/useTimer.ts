import { useState, useRef, useCallback, useEffect } from 'react'

export function useTimer(startTime: string | null) {
  const [elapsed, setElapsed] = useState(0)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const start = useCallback(() => {
    if (intervalRef.current) return
    intervalRef.current = setInterval(() => {
      if (startTime) {
        const start = new Date(startTime).getTime()
        setElapsed(Date.now() - start)
      }
    }, 1000)
  }, [startTime])

  const stop = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
  }, [])

  useEffect(() => {
    if (startTime) {
      start()
    }
    return stop
  }, [startTime, start, stop])

  const formatTime = (ms: number) => {
    const totalSec = Math.floor(ms / 1000)
    const min = Math.floor(totalSec / 60)
    const sec = totalSec % 60
    return `${min.toString().padStart(2, '0')}:${sec.toString().padStart(2, '0')}`
  }

  return { elapsed, formatted: formatTime(elapsed), start, stop }
}
