import { ChevronDown } from 'lucide-react'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { splitFirstSentence } from '@/lib/text'
import { cn } from '@/lib/utils'

/**
 * Extra explanation that stays folded until the reader asks for it, so that each screen shows one
 * headline and one short line. A native <details> element keeps the text in the page for screen
 * readers and for search, and it works without JavaScript.
 */
export function LearnMore({ children, className }: { children: ReactNode; className?: string }) {
  const { t } = useTranslation()
  return (
    <details className={cn('group/more', className)}>
      <summary className="inline-flex w-fit cursor-pointer list-none items-center gap-1 rounded-full text-base font-medium text-primary outline-none focus-visible:ring-3 focus-visible:ring-ring/50 [&::-webkit-details-marker]:hidden">
        <span className="group-open/more:hidden">{t('common.learnMore')}</span>
        <span className="hidden group-open/more:inline">{t('common.showLess')}</span>
        <ChevronDown
          aria-hidden
          className="size-4 transition-transform duration-200 ease-out-strong group-open/more:rotate-180"
        />
      </summary>
      <div className="mt-3 grid gap-3 text-base text-muted-foreground">{children}</div>
    </details>
  )
}

/** The first sentence of a text stays visible, and the rest folds into "Learn more". */
export function Lede({ text, className }: { text: string; className?: string }) {
  const [first, rest] = splitFirstSentence(text)
  return (
    <div className={cn('grid gap-2', className)}>
      <p className="text-lg text-muted-foreground">{first}</p>
      {rest && (
        <LearnMore>
          <p>{rest}</p>
        </LearnMore>
      )}
    </div>
  )
}

/** The title of a screen, in the large display size, with a short line under it. */
export function PageHeader({ title, lede, level = 1 }: { title: string; lede?: string; level?: 1 | 2 }) {
  const Heading = level === 1 ? 'h1' : 'h2'
  return (
    <header className="grid gap-3">
      <Heading className="text-4xl leading-[1.08] font-semibold tracking-[-0.022em] md:text-5xl">
        {title}
      </Heading>
      {lede && <Lede text={lede} className="max-w-[62ch]" />}
    </header>
  )
}
