import { readFile, readdir } from 'node:fs/promises'
import path from 'node:path'
import { describe, expect, it } from 'vitest'
import {
  LEGACY_TSX_CLASS_NAMES,
  MAX_LEGACY_BADGE,
  INDEX_CSS_LEGACY_GLOBALS_TODO,
  countLegacyBadgeInLine,
  countLegacyBadgeInTsx,
  hasLegacyBtnToken,
  hasLegacyCardToken,
  lineUsesLegacyMutedClass,
  lineUsesLegacyRowClass,
  lineUsesLegacyStackClass,
  lineUsesLegacyTsxClassName,
  validateIndexCss,
  validateListRowTsx,
  validateTypesetCss,
} from '../../scripts/ui-migration-rules.mjs'

const WEB_ROOT = path.join(import.meta.dirname, '../..')

async function readWeb(relative: string) {
  return readFile(path.join(WEB_ROOT, relative), 'utf8')
}

async function walkTsx(dir: string, out: string[] = []): Promise<string[]> {
  for (const ent of await readdir(dir, { withFileTypes: true })) {
    const p = path.join(dir, ent.name)
    if (ent.isDirectory()) {
      if (ent.name === 'node_modules') continue
      await walkTsx(p, out)
    } else if (ent.name.endsWith('.tsx')) {
      out.push(p)
    }
  }
  return out
}

describe('legacy UI guards (shared with check:ui)', () => {
  it('validateIndexCss passes on committed index.css', async () => {
    const indexCss = await readWeb('src/index.css')
    expect(validateIndexCss(indexCss)).toEqual([])
  })

  it('validateTypesetCss passes on committed typeset.css', async () => {
    const typesetCss = await readWeb('src/typeset.css')
    expect(validateTypesetCss(typesetCss)).toEqual([])
  })

  it('validateListRowTsx passes on ListRow.tsx', async () => {
    const listRow = await readWeb('src/components/ListRow.tsx')
    expect(validateListRowTsx(listRow)).toEqual([])
  })

  it.each([
    ['.btn global rule', '.btn { padding: 0.5rem; }', 'legacy .btn'],
    ['.stack global rule', '.stack { display: flex; }', 'legacy .stack'],
    ['.row global rule', '.row { display: flex; }', 'legacy .row'],
    ['.grow global rule', '.grow { flex: 1; }', 'legacy .grow'],
    ['.muted global rule', '.muted { color: gray; }', 'legacy .muted'],
    ['.item-meta selector', '.item-meta { margin: 0; }', '.item-meta'],
    ['.summary-md class', '.summary-md { font-size: 1rem; }', '.summary-md'],
  ])('validateIndexCss rejects %s', (_label, snippet, needle) => {
    const issues = validateIndexCss(snippet)
    expect(issues.some((msg) => msg.includes(needle))).toBe(true)
  })

  it('tracks remaining legacy index.css globals for a follow-up migration', async () => {
    const indexCss = await readWeb('src/index.css')
    for (const token of INDEX_CSS_LEGACY_GLOBALS_TODO) {
      expect(indexCss.includes(token)).toBe(true)
    }
  })

  it('detects legacy btn/card tokens in className strings', () => {
    expect(hasLegacyBtnToken('foo btn bar')).toBe(true)
    expect(hasLegacyBtnToken('button-outline')).toBe(false)
    expect(hasLegacyCardToken('panel card shadow')).toBe(true)
    expect(hasLegacyCardToken('cardboard')).toBe(false)
  })

  it('counts legacy badge className usages per line', () => {
    expect(countLegacyBadgeInLine('<span className="badge">')).toBe(1)
    expect(countLegacyBadgeInLine('className="foo badge bar badge"')).toBe(1)
    expect(countLegacyBadgeInLine('className="HubBadge"')).toBe(0)
  })

  it.each([
    ['stack', 'className="stack gap-2"', lineUsesLegacyStackClass],
    ['row', 'className="row items-center"', lineUsesLegacyRowClass],
    ['muted', 'className="foo muted bar"', lineUsesLegacyMutedClass],
  ])('detects legacy %s layout class in TSX line', (_name, line, detector) => {
    expect(detector(line)).toBe(true)
    expect(detector('className="flex flex-wrap gap-2"')).toBe(false)
  })

  it.each(LEGACY_TSX_CLASS_NAMES)('documents legacy TSX class guard: %s', (legacyClass) => {
    const sample = `className="${legacyClass}"`
    expect(lineUsesLegacyTsxClassName(sample, legacyClass)).toBe(true)
  })

  it('keeps legacy badge cap across src/**/*.tsx', async () => {
    const srcDir = path.join(WEB_ROOT, 'src')
    const files = await walkTsx(srcDir)
    let total = 0
    for (const file of files) {
      total += countLegacyBadgeInTsx(await readFile(file, 'utf8'))
    }
    expect(total).toBeLessThanOrEqual(MAX_LEGACY_BADGE)
  })
})
