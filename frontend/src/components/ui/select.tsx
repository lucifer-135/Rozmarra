import { Check, ChevronDown } from 'lucide-react'
import { Select as SelectPrimitive } from 'radix-ui'

export interface SelectOption {
  value: string
  label: string
}

/**
 * A select box whose chosen text wraps onto a second line instead of being cut off. A native
 * select cannot wrap, and some names of fasts and foods are full sentences that must not be cut.
 */
export function WrappingSelect({
  id,
  value,
  options,
  onValueChange,
  disabled,
}: {
  id: string
  value: string
  options: SelectOption[]
  onValueChange: (value: string) => void
  disabled?: boolean
}) {
  return (
    <SelectPrimitive.Root value={value} onValueChange={onValueChange} disabled={disabled}>
      <SelectPrimitive.Trigger
        id={id}
        className="flex min-h-9 w-full items-center justify-between gap-2 rounded-md border border-input bg-background px-2 py-1.5 text-left text-base outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50"
      >
        <SelectPrimitive.Value className="min-w-0 flex-1 whitespace-normal" />
        <SelectPrimitive.Icon asChild>
          <ChevronDown aria-hidden className="size-4 shrink-0 opacity-60" />
        </SelectPrimitive.Icon>
      </SelectPrimitive.Trigger>
      <SelectPrimitive.Portal>
        <SelectPrimitive.Content
          data-slot="select-content"
          position="popper"
          sideOffset={4}
          className="z-50 max-h-[var(--radix-select-content-available-height)] w-[var(--radix-select-trigger-width)] origin-[var(--radix-select-content-transform-origin)] overflow-hidden rounded-md border bg-popover text-popover-foreground shadow-md duration-150 ease-out-strong data-[state=closed]:duration-100 data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-[0.97] data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-[0.97]"
        >
          <SelectPrimitive.Viewport className="p-1">
            {options.map((option) => (
              <SelectPrimitive.Item
                key={option.value}
                value={option.value}
                className="relative flex cursor-default items-start rounded-sm py-1.5 pr-2 pl-8 text-base outline-none select-none data-[highlighted]:bg-muted"
              >
                <span className="absolute top-2.5 left-2">
                  <SelectPrimitive.ItemIndicator>
                    <Check aria-hidden className="size-4" />
                  </SelectPrimitive.ItemIndicator>
                </span>
                <SelectPrimitive.ItemText>{option.label}</SelectPrimitive.ItemText>
              </SelectPrimitive.Item>
            ))}
          </SelectPrimitive.Viewport>
        </SelectPrimitive.Content>
      </SelectPrimitive.Portal>
    </SelectPrimitive.Root>
  )
}
