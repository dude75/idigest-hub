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

  it('renders unit badge when provided', () => {
    render(<StatCard label="Growth" value="12" unit="+12%" />)
    expect(screen.getByText('+12%')).toBeInTheDocument()
  })

  it('shows footer lines for title and footer props', () => {
    render(
      <StatCard
        label="Age"
        value="1h"
        title="2026-03-01 12:00"
        footer="Trending up"
      />,
    )
    expect(screen.getByText('Trending up')).toBeInTheDocument()
    expect(screen.getByText('2026-03-01 12:00')).toBeInTheDocument()
  })

  it('applies proxy tone class on value', () => {
    render(<StatCard label="Proxy" value="OK" tone="proxy-up" />)
    expect(screen.getByText('OK')).toHaveClass('stat-proxy-up')
  })
})
