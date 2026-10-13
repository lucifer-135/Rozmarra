import type { ReactNode } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/lib/utils'

export function Section({
  title,
  description,
  children,
  className,
  action,
}: {
  title: string
  description?: ReactNode
  children: ReactNode
  className?: string
  action?: ReactNode
}) {
  return (
    <Card className={cn('gap-4', className)}>
      <CardHeader className="flex flex-wrap items-start justify-between gap-3">
        <div className="grid gap-1">
          <CardTitle>
            <h2 className="text-xl font-semibold">{title}</h2>
          </CardTitle>
          {description && (
            <CardDescription className="text-base">{description}</CardDescription>
          )}
        </div>
        {action}
      </CardHeader>
      <CardContent className="grid gap-4 text-base">{children}</CardContent>
    </Card>
  )
}

/** A list of labels and values, laid out in two columns. */
export function Facts({ items }: { items: [string, ReactNode][] }) {
  return (
    <dl className="grid grid-cols-1 gap-x-6 gap-y-2 sm:grid-cols-[minmax(10rem,auto)_1fr]">
      {items.map(([label, value]) => (
        <div key={label} className="contents">
          <dt className="text-muted-foreground">{label}</dt>
          <dd className="font-medium">{value}</dd>
        </div>
      ))}
    </dl>
  )
}

/** A single number with its label, for example the average glucose over 14 days. */
export function StatTile({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="rounded-lg border bg-background p-4">
      <p className="text-base text-muted-foreground">{label}</p>
      <p className="mt-1 text-2xl font-semibold">{value}</p>
      {note && <p className="mt-1 text-base text-muted-foreground">{note}</p>}
    </div>
  )
}
