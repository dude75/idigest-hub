import { readFile } from 'node:fs/promises'
import path from 'node:path'
import { describe, expect, it } from 'vitest'

const WEB_ROOT = path.join(import.meta.dirname, '../..')

async function readWeb(relative: string) {
  return readFile(path.join(WEB_ROOT, relative), 'utf8')
}

describe('Typeset UI contract', () => {
  it('uses 16px Geist base on :root for the whole app', async () => {
    const indexCss = await readWeb('src/index.css')
    expect(indexCss).toMatch(/:root\s*\{[\s\S]*--typeset-size:\s*16px/)
    expect(indexCss).toMatch(/:root\s*\{[\s\S]*font-size:\s*var\(--typeset-size\)/)
    expect(indexCss).not.toContain('calc(14px * 1.05)')
  })

  it('wires typeset.css, Geist Mono, and a single typeset-app preset', async () => {
    const indexCss = await readWeb('src/index.css')
    expect(indexCss).toContain('@import "./typeset.css"')
    expect(indexCss).toContain('@import "@fontsource-variable/geist-mono"')
    expect(indexCss).toContain('--font-sans: var(--font-geist)')
    expect(indexCss).toContain('--font-mono: var(--font-geist-mono)')
    expect(indexCss).not.toMatch(/Inter,\s*ui-sans-serif/)

    const presetMatches = indexCss.match(/\.typeset-app\s*\{/g)
    expect(presetMatches).toHaveLength(1)
    expect(indexCss).toMatch(/\.typeset-app\s*\{[\s\S]*--typeset-font-body:\s*var\(--font-sans\)/)
    expect(indexCss).toMatch(/\.typeset-app\s*\{[\s\S]*--typeset-size:\s*16px/)
  })

  it('applies typeset on document body', async () => {
    const html = await readWeb('index.html')
    expect(html).toMatch(/<body[^>]*class="[^"]*\btypeset\b/)
    expect(html).toMatch(/<body[^>]*class="[^"]*\btypeset-app\b/)
  })

  it('unifies reading typography utilities', async () => {
    const indexCss = await readWeb('src/index.css')
    expect(indexCss).not.toContain('.summary-md')
    expect(indexCss).toMatch(
      /\.hub-reading-surface,\s*\n\s*\.summary-body,\s*\n\s*\.agreement-text\s*\{[\s\S]*font-family:\s*var\(--font-sans\)\s*!important/,
    )
    expect(indexCss).not.toMatch(/font-family:\s*ui-monospace/)
  })

  it('ships shadcn typeset stylesheet with scroll helper', async () => {
    const typesetCss = await readWeb('src/typeset.css')
    expect(typesetCss).toContain('.typeset-scroll')
  })

  it('uses scaled hub content column on .page', async () => {
    const indexCss = await readWeb('src/index.css')
    expect(indexCss).toContain('--hub-content-scale: 1.1')
    expect(indexCss).toContain('--hub-page-max: calc(67.5rem * var(--hub-content-scale))')
    expect(indexCss).toContain('--hub-shell-max: var(--hub-page-max)')
    expect(indexCss).toMatch(/\.page\s*\{[^}]*max-width:\s*var\(--hub-page-max\)/)
    expect(indexCss).not.toContain('max-width: 1080px')
  })

  it('keeps entity back layout on CSS grid without JS offset', async () => {
    const indexCss = await readWeb('src/index.css')
    expect(indexCss).toMatch(/\.entity-page-main\s*\{[^}]*display:\s*contents/)
    expect(indexCss).toMatch(/\.entity-page-layout:has\([\s\S]*?\)\s*\.entity-back\s*\{[^}]*grid-row:\s*2/)
    expect(indexCss).not.toContain('--entity-back-offset')
    expect(indexCss).not.toContain('entity-back-offset')
  })

  it('declares Geist Mono in theme and package deps', async () => {
    const indexCss = await readWeb('src/index.css')
    expect(indexCss).toMatch(/@theme inline\s*\{[\s\S]*--font-mono:\s*var\(--font-geist-mono\)/)

    const pkg = await readWeb('package.json')
    expect(pkg).toContain('@fontsource-variable/geist-mono')
  })

  it('scopes typeset list styles to reading surfaces only', async () => {
    const typesetCss = await readWeb('src/typeset.css')
    expect(typesetCss).toMatch(
      /\.typeset :where\(\.hub-reading-surface, \.summary-body, \.agreement-text\) :where\(ul\)/,
    )
  })

  it('shares list row typography with admin tables via appTypography', async () => {
    const listRow = await readWeb('src/components/ListRow.tsx')
    const adminTable = await readWeb('src/components/app/AdminDataTable.tsx')
    const tokens = await readWeb('src/components/app/appTypography.ts')
    expect(tokens).toContain('export const appPrimaryText')
    expect(listRow).toContain('listRowChrome')
    expect(listRow).toContain('appListRowTitle')
    expect(await readWeb('src/index.css')).not.toContain('.row {')
    expect(await readWeb('src/index.css')).not.toContain('.item {')
    expect(await readWeb('src/index.css')).not.toContain('.group {')
    expect(await readWeb('src/index.css')).not.toContain('public-link-meta-item')
    expect(await readWeb('src/index.css')).not.toContain('tariff-rates-line')
    expect(await readWeb('src/index.css')).not.toContain('audit-payload')
    expect(adminTable).toContain('appPrimaryText')
    expect(await readWeb('src/index.css')).not.toContain('.item a.title')
    expect(await readWeb('src/index.css')).not.toContain('.entity-title')
    expect(await readWeb('src/index.css')).not.toContain('.stats-chart-title')
    expect(await readWeb('src/index.css')).not.toContain('.org-ledger-modal')
    expect(await readWeb('src/index.css')).not.toContain('.landing-lead')
    expect(await readWeb('src/index.css')).not.toContain('.landing-eyebrow')
    expect(await readWeb('src/index.css')).not.toContain('.landing-trust-label')
    expect(await readWeb('src/index.css')).not.toContain('.stats-empty')
    expect(await readWeb('src/index.css')).not.toMatch(/\.muted\s*\{/)
    expect(await readWeb('src/index.css')).not.toMatch(/hub-muted/)
  })

  it('routes UI durations through AppDuration', async () => {
    const ledger = await readWeb('src/components/OrgLedgerModal.tsx')
    const statsGrid = await readWeb('src/components/StatsSummaryGrid.tsx')
    expect(ledger).toContain('AppDuration')
    expect(statsGrid).toContain('AppDuration')
    expect(await readWeb('src/components/app/AppDuration.tsx')).toContain('formatAudioTime')
  })
})
