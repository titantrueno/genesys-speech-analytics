export function StatusBadge({ label, className }: { label: string; className: string }) {
  return <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap ${className}`}>{label}</span>
}
