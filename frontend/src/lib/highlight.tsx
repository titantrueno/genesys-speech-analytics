import type { ReactNode } from 'react'

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

export function highlight(text: string, keywords: string[]): ReactNode[] {
  const terms = keywords.filter(Boolean).sort((a, b) => b.length - a.length)
  if (terms.length === 0) return [text]
  const pattern = new RegExp(`(${terms.map(escapeRegExp).join('|')})`, 'gi')
  return text.split(pattern).map((part, i) =>
    i % 2 === 1
      ? <mark key={i} className="rounded bg-amber-100 px-0.5 text-inherit">{part}</mark>
      : part,
  )
}
