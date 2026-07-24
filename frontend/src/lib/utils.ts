import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatDate(iso: string | null): string {
  if (!iso) return '-'
  const d = new Date(iso)
  return d.toLocaleString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  })
}

export function formatDuration(ms: number): string {
  if (!ms) return '-'
  const sec = Math.floor(ms / 1000)
  const min = Math.floor(sec / 60)
  const h = Math.floor(min / 60)
  if (h > 0) return `${h}小时${min % 60}分钟`
  return `${min}分钟${sec % 60}秒`
}
