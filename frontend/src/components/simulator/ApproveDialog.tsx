import { CircleCheck, LoaderCircle } from 'lucide-react'
import { useId, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

// The doctor approves a plan before Rozmarra can print it (FR-D5). The approval records the
// doctor's name and the date.

interface Props {
  planName: string
  disabled?: boolean
  busy?: boolean
  error?: string | null
  onApprove: (doctorName: string, contact: string) => Promise<unknown>
}

export function ApproveDialog({ planName, disabled, busy, error, onApprove }: Props) {
  const { t } = useTranslation()
  const id = useId()
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const [contact, setContact] = useState('')
  const empty = name.replace(/^dr\b\.?\s*/i, '').trim() === ''

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button disabled={disabled} className="text-base">
          <CircleCheck aria-hidden />
          {t('approve.button')}{' '}
          <span className="sr-only">{t('approve.buttonContext', { plan: planName })}</span>
        </Button>
      </DialogTrigger>
      <DialogContent showCloseButton={false} className="text-base">
        <form
          className="grid gap-4"
          onSubmit={(e) => {
            e.preventDefault()
            if (empty) return
            void onApprove(name.trim(), contact.trim()).then(() => setOpen(false), () => undefined)
          }}
        >
          <DialogHeader>
            <DialogTitle className="text-xl">{t('approve.title', { plan: planName })}</DialogTitle>
            <DialogDescription className="text-base">{t('approve.description')}</DialogDescription>
          </DialogHeader>
          <div className="grid gap-1">
            <Label htmlFor={`${id}-doctor`} className="text-base">
              {t('approve.doctorName')}
            </Label>
            <Input
              id={`${id}-doctor`}
              className="text-base md:text-base"
              autoComplete="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={t('approve.placeholder')}
            />
            <p className="text-muted-foreground">{t('approve.nameHelp')}</p>
          </div>
          <div className="grid gap-1">
            <Label htmlFor={`${id}-contact`} className="text-base">
              {t('approve.contact')}
            </Label>
            <Input
              id={`${id}-contact`}
              className="text-base md:text-base"
              value={contact}
              maxLength={200}
              onChange={(e) => setContact(e.target.value)}
              placeholder={t('approve.contactPlaceholder')}
            />
            <p className="text-muted-foreground">{t('approve.contactHelp')}</p>
          </div>
          {error && (
            <p role="alert" className="text-destructive">
              {error}
            </p>
          )}
          <DialogFooter>
            <Button type="button" variant="outline" className="text-base" onClick={() => setOpen(false)}>
              {t('common.cancel')}
            </Button>
            <Button type="submit" disabled={empty || busy} className="text-base">
              {busy ? <LoaderCircle aria-hidden className="animate-spin" /> : <CircleCheck aria-hidden />}
              {t('approve.confirm')}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
