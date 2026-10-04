import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { StatCard } from './StatCard'

vi.mock('@/components/app/AppHoverHint', () => ({
  AppHoverHint: ({ children }: { children: React.ReactNode }) => children,
}))

describe('StatCard', () => {
  it('renders label and value', () => {
    render(<StatCard label="Total keys" value="2" />)
    expect(screen.getByText('Total keys')).toBeInTheDocument()
    expect(screen.getByText('2')).toBeInTheDocument()
  })

  it('shows footer inline and keeps title for hover hint only', () => {
    render(
      <StatCard
        label="Age"
        value="1h"
        title="2026-03-01 12:00"
        footer="Trending up"
      />,
    )
    expect(screen.getByText('Trending up')).toBeInTheDocument()
    expect(screen.queryByText('2026-03-01 12:00')).not.toBeInTheDocument()
  })

  it('applies proxy tone class on value', () => {
    render(<StatCard label="Proxy" value="OK" tone="proxy-up" />)
    expect(screen.getByText('OK')).toHaveClass('stat-proxy-up')
  })
})
