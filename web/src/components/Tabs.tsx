import { NavLink } from 'react-router-dom'

export type TabLinkItem = { id: string; label: string; to: string; end?: boolean }
export type TabButtonItem = { id: string; label: string; active: boolean; onClick: () => void }

type TabItem = TabLinkItem | TabButtonItem

type Props = {
  items: TabItem[]
  ariaLabel?: string
}

function isLink(item: TabItem): item is TabLinkItem {
  return 'to' in item
}

export function Tabs({ items, ariaLabel }: Props) {
  return (
    <div className="tabs" role="tablist" aria-label={ariaLabel}>
      {items.map((item) => {
        if (isLink(item)) {
          return (
            <NavLink
              key={item.id}
              to={item.to}
              end={item.end}
              className={({ isActive }) => (isActive ? 'active' : '')}
            >
              {item.label}
            </NavLink>
          )
        }
        return (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={item.active}
            className={item.active ? 'active' : ''}
            onClick={item.onClick}
          >
            {item.label}
          </button>
        )
      })}
    </div>
  )
}
