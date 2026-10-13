import { CircleAlert, LoaderCircle } from 'lucide-react'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'

// The loading and error states of a request, with words as well as icons.

export function Loading({ text }: { text?: string }) {
  const { t } = useTranslation()
  return (
    <p role="status" className="flex items-center gap-2 py-6 text-base text-muted-foreground">
      <LoaderCircle aria-hidden className="size-5 animate-spin" />
      {text ?? t('common.loading')}
    </p>
  )
}

export function LoadError({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const { t } = useTranslation()
  const message = error instanceof Error ? error.message : t('common.errorBody')
  return (
    <Alert variant="destructive" className="my-4">
      <CircleAlert aria-hidden />
      <AlertTitle className="text-base">{t('common.errorTitle')}</AlertTitle>
      <AlertDescription className="text-base">
        <p>{message}</p>
        {onRetry && (
          <Button variant="outline" className="mt-2" onClick={onRetry}>
            {t('common.retry')}
          </Button>
        )}
      </AlertDescription>
    </Alert>
  )
}

interface QueryLike<T> {
  data: T | undefined
  error: unknown
  isPending: boolean
  refetch: () => unknown
}

/** Shows the loading or error state of a query, or its content when the data is ready. */
export function QueryState<T>({
  query,
  children,
  loadingText,
}: {
  query: QueryLike<T>
  children: (data: T) => ReactNode
  loadingText?: string
}) {
  if (query.isPending) return <Loading text={loadingText} />
  if (query.error || query.data === undefined) {
    return <LoadError error={query.error} onRetry={() => void query.refetch()} />
  }
  return <>{children(query.data)}</>
}
