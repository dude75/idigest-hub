import { useCallback, useRef, useState, type MouseEvent, type ReactNode } from 'react'
import { createPortal } from 'react-dom'

const OFFSET_X = 12
const OFFSET_Y = 16

type AppCursorHintProps = {
  content?: ReactNode
  children: ReactNode
  className?: string
  onClick?: (e: MouseEvent<HTMLDivElement>) => void
}

/** Tooltip that follows the pointer (for dense lists, e.g. transcript lines). */
export function AppCursorHint({ content, children, className, onClick }: AppCursorHintProps) {
  const [tip, setTip] = useState<{ x: number; y: number } | null>(null)
  const rafRef = useRef<number | null>(null)

  const showAt = useCallback((clientX: number, clientY: number) => {
    if (rafRef.current != null) cancelAnimationFrame(rafRef.current)
    rafRef.current = requestAnimationFrame(() => {
      setTip({ x: clientX + OFFSET_X, y: clientY + OFFSET_Y })
    })
  }, [])

  const hide = useCallback(() => {
    if (rafRef.current != null) cancelAnimationFrame(rafRef.current)
    setTip(null)
  }, [])

  if (content == null || content === '') {
    return <>{children}</>
  }

  return (
    <>
      <div
        className={className}
        onClick={onClick}
        onPointerEnter={(e) => showAt(e.clientX, e.clientY)}
        onPointerMove={(e) => showAt(e.clientX, e.clientY)}
        onPointerLeave={hide}
      >
        {children}
      </div>
      {tip &&
        createPortal(
          <div className="app-cursor-hint" style={{ left: tip.x, top: tip.y }} role="tooltip">
            {content}
          </div>,
          document.body,
        )}
    </>
  )
}
