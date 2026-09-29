import type { ReactNode } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/lib/utils'

type Props = {
  title: ReactNode
  children: ReactNode
  className?: string
  description?: ReactNode
}

export function AuthCard({ title, children, className, description }: Props) {
  return (
    <Card className={cn('auth-card w-full max-w-[420px]', className)}>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        {description ? <CardDescription>{description}</CardDescription> : null}
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  )
}
