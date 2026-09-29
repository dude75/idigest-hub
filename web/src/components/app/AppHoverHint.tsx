import { cloneElement, isValidElement, type ReactElement, type ReactNode } from 'react'
import { HoverCard, HoverCardContent, HoverCardTrigger } from '@/components/ui/hover-card'
import { cn } from '@/lib/utils'

type AppHoverHintProps = {
  content?: ReactNode
  children: ReactElement | ReactNode
  className?: string
  contentClassName?: string
  side?: 'top' | 'right' | 'bottom' | 'left'
}

/** shadcn HoverCard wrapper for control hints (replaces native `title` tooltips). */
export function AppHoverHint({
  content,
  children,
  className,
  contentClassName,
  side = 'bottom',
}: AppHoverHintProps) {
  if (content == null || content === '') {
    return <>{children}</>
  }

  const triggerEl: ReactElement<{ className?: string; children?: ReactNode; title?: string }> = isValidElement(
    children,
  )
    ? (children as ReactElement<{ className?: string; children?: ReactNode; title?: string }>)
    : <span className="inline-flex">{children}</span>

  return (
    <HoverCard>
      <HoverCardTrigger
        delay={300}
        closeDelay={100}
        render={cloneElement(triggerEl, {
          title: undefined,
          className: cn(triggerEl.props.className, className),
        })}
      >
        {triggerEl.props.children}
      </HoverCardTrigger>
      <HoverCardContent side={side} className={cn('max-w-sm text-pretty font-normal', contentClassName)}>
        {content}
      </HoverCardContent>
    </HoverCard>
  )
}
