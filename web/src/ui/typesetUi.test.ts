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
    expect(indexCss).toContain('--hub-content-scale: 1.2')
    expect(indexCss).toContain('--hub-page-max: calc(67.5rem * var(--hub-content-scale))')
    expect(indexCss).toMatch(/\.page\s*\{[^}]*max-width:\s*var\(--hub-page-max\)/)
    expect(indexCss).not.toContain('max-width: 1080px')
  })

  it('declares Geist Mono in theme and package deps', async () => {
    const indexCss = await readWeb('src/index.css')
    expect(indexCss).toMatch(/@theme inline\s*\{[\s\S]*--font-mono:\s*var\(--font-geist-mono\)/)

    const pkg = await readWeb('package.json')
    expect(pkg).toContain('@fontsource-variable/geist-mono')
  })
})
