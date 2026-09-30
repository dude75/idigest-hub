#!/usr/bin/env node
/**
 * Guards shadcn migration: fails CI on patterns that caused cascade/layout regressions.
 * Run: npm run check:ui
 *
 * New UI code: shadcn primitives + App* wrappers; primary save/create → AppSubmitButton.
 * Layout: prefer Tailwind (flex/grid/gap) over new `.stack` / `.row` in TSX.
 */
import { access, readdir, readFile } from 'node:fs/promises'
import path from 'node:path'

const SRC = path.join(import.meta.dirname, '../src')
const ALLOW_UI_TABS = new Set([
  path.join(SRC, 'components/Tabs.tsx'),
  path.join(SRC, 'components/ui/tabs.tsx'),
])

/** Modal confirm — not a settings save row. */
const ALLOW_RAW_SUBMIT_BUTTON = new Set([
  path.join(SRC, 'pages/instance/WorkerImpactModal.tsx'),
])

/** Legacy `.badge` in className — use HubBadge. */
const MAX_LEGACY_BADGE = 0

/** Intentional `.stack` (share panel grid, stats filters). */
const ALLOW_STACK_CLASS = new Set([
  path.join(SRC, 'components/ShareDialog.tsx'),
  path.join(SRC, 'components/StatsFiltersPanel.tsx'),
])

/** Copy control — only inside AppUrlCopyRow. */
const ALLOW_PUBLIC_LINK_COPY = new Set([path.join(SRC, 'components/app/AppUrlCopyRow.tsx')])

const SUBMIT_LABEL_RE =
  /t\(['"](?:common\.(?:save|create)|instance\.(?:legalDocumentsSave|landingExtraSave))['"]\)/

const issues = []

async function walk(dir, out = []) {
  for (const ent of await readdir(dir, { withFileTypes: true })) {
    const p = path.join(dir, ent.name)
    if (ent.isDirectory()) {
      if (ent.name === 'node_modules') continue
      await walk(p, out)
    } else if (ent.name.endsWith('.tsx')) out.push(p)
  }
  return out
}

function rel(p) {
  return path.relative(path.join(import.meta.dirname, '..'), p)
}

function hasLegacyCardToken(classFragment) {
  return /(?:^|\s)card(?:\s|$)/.test(classFragment)
}

function hasLegacyBtnToken(classFragment) {
  return /(?:^|\s)btn(?:\s|$)/.test(classFragment)
}

const files = await walk(SRC)
let legacyBadgeCount = 0

for (const file of files) {
  const text = await readFile(file, 'utf8')
  const lines = text.split('\n')

  if (
    text.includes('@/components/ui/tabs') &&
    !ALLOW_UI_TABS.has(file)
  ) {
    issues.push(`${rel(file)}: import ui/tabs directly — use components/Tabs.tsx`)
  }

  lines.forEach((line, i) => {
    const btnClass = line.match(/<Button\b[^>]*className=["']([^"']+)["']/)
    if (btnClass && hasLegacyBtnToken(btnClass[1])) {
      issues.push(`${rel(file)}:${i + 1}: shadcn Button must not use legacy class "btn"`)
    }
    if (/<Button\b/.test(line) && /className=["'][^"']*\bdanger\b/.test(line)) {
      issues.push(
        `${rel(file)}:${i + 1}: use Button variant="destructive" — not legacy class "danger"`,
      )
    }
    if (/public-link-copy/.test(line) && !ALLOW_PUBLIC_LINK_COPY.has(file)) {
      issues.push(
        `${rel(file)}:${i + 1}: use AppUrlCopyRow for copy — do not use class "public-link-copy" on Button`,
      )
    }
    if (/sso-url-copy/.test(line)) {
      issues.push(`${rel(file)}:${i + 1}: legacy sso-url-copy — use AppUrlCopyRow`)
    }
    const stackClass = line.match(/className=["']([^"']+)["']/)
    if (
      stackClass &&
      /(?:^|\s)stack(?:\s|$)/.test(stackClass[1]) &&
      !ALLOW_STACK_CLASS.has(file)
    ) {
      issues.push(
        `${rel(file)}:${i + 1}: legacy "stack" layout — use flex flex-col gap-3 (Tailwind)`,
      )
    }
    if (
      file.includes(`${path.sep}pages${path.sep}`) &&
      stackClass &&
      /(?:^|\s)row(?:\s|$)/.test(stackClass[1]) &&
      !stackClass[1].includes('check-row') &&
      !stackClass[1].includes('share-picker-row') &&
      !stackClass[1].includes('AppCheckboxRow')
    ) {
      issues.push(
        `${rel(file)}:${i + 1}: legacy "row" layout in pages — use flex flex-wrap items-center gap-2`,
      )
    }
    if (
      /<Button\b/.test(line) &&
      !/<ButtonLink\b/.test(line) &&
      /className=["'][^"']*-btn\b/.test(line) &&
      !line.includes('inline-rename-btn')
    ) {
      issues.push(
        `${rel(file)}:${i + 1}: shadcn Button uses legacy *-btn class — use variant/size/Tailwind utilities`,
      )
    }
    const tabsClass = line.match(/className=["']([^"']+)["']/)
    if (tabsClass && /(?:^|\s)tabs(?:\s|$)/.test(tabsClass[1]) && !tabsClass[1].includes('library-tabs')) {
      issues.push(`${rel(file)}:${i + 1}: legacy "tabs" class — use components/Tabs or ui/tabs`)
    }
    if (line.includes('stats-table') && !file.includes('check-ui-migration')) {
      issues.push(`${rel(file)}:${i + 1}: legacy stats-table — use AdminDataTable (shadcn Table)`)
    }
    if (/type=["']date["']/.test(line)) {
      issues.push(`${rel(file)}:${i + 1}: native type="date" — use AppDateField (shadcn Calendar)`)
    }
    if (/<select\b/.test(line) || /AuthSelect\b/.test(line)) {
      issues.push(`${rel(file)}:${i + 1}: native select — use AppSelect / AppSelectField (shadcn Select)`)
    }
    if (/<option\b/.test(line)) {
      issues.push(`${rel(file)}:${i + 1}: native option — use AppSelect options prop`)
    }
    const badgeMatches = line.match(/className=["'][^"']*\bbadge\b/g)
    if (badgeMatches) legacyBadgeCount += badgeMatches.length

    const quotedClass = line.match(/className=["']([^"']+)["']/)
    if (quotedClass && hasLegacyCardToken(quotedClass[1])) {
      issues.push(`${rel(file)}:${i + 1}: legacy "card" class — use @/components/ui/card or Admin*Card`)
    }
    if (line.includes('className={cn(') && hasLegacyCardToken(line)) {
      const cnMatch = line.match(/cn\([^)]*\)/)
      if (cnMatch && /['"`][^'"`]*(?:^|\s)card(?:\s|$)/.test(cnMatch[0])) {
        issues.push(`${rel(file)}:${i + 1}: legacy "card" class — use @/components/ui/card or Admin*Card`)
      }
    }

    if (
      SUBMIT_LABEL_RE.test(line) &&
      !ALLOW_RAW_SUBMIT_BUTTON.has(file) &&
      !line.includes('confirmLabel')
    ) {
      const window = lines.slice(Math.max(0, i - 10), i + 1).join('\n')
      if (!window.includes('AppSubmitButton')) {
        issues.push(
          `${rel(file)}:${i + 1}: form save/create must use AppSubmitButton (ready=…) — not raw Button`,
        )
      }
    }
  })
}

if (legacyBadgeCount > MAX_LEGACY_BADGE) {
  issues.push(
    `legacy .badge usages (${legacyBadgeCount}) exceed cap ${MAX_LEGACY_BADGE} — migrate to HubBadge`,
  )
}

const indexCss = await readFile(path.join(SRC, 'index.css'), 'utf8')
const authShell = await readFile(path.join(import.meta.dirname, '../public/auth-shell.css'), 'utf8')
const hubAccent = indexCss.match(/--hub-accent:\s*([^;]+);/)?.[1]?.trim()
const authPrimary = authShell.match(/^\s*--primary:\s*([^;]+);/m)?.[1]?.trim()
if (hubAccent && authPrimary && authPrimary !== hubAccent) {
  issues.push(
    `auth-shell.css --primary must match index.css --hub-accent (${hubAccent}), got ${authPrimary}`,
  )
}
for (const font of ['geist-latin.woff2', 'geist-cyrillic.woff2']) {
  try {
    await access(path.join(import.meta.dirname, '../public/fonts', font))
  } catch {
    issues.push(`missing web/public/fonts/${font} — OAuth auth-shell Geist @font-face`)
  }
}

const oauthPagesPath = path.join(import.meta.dirname, '../../app/services/oauth_pages.py')
const oauthPages = await readFile(oauthPagesPath, 'utf8')
if (!oauthPages.includes('auth-shell.js')) {
  issues.push('oauth_pages.py must load /auth-shell.js for popup selects on OAuth HTML')
}
if (!authShell.includes('.hub-select-trigger')) {
  issues.push('auth-shell.css must define .hub-select-* popup select styles')
}
try {
  await access(path.join(import.meta.dirname, '../public/auth-shell.js'))
} catch {
  issues.push('missing web/public/auth-shell.js — OAuth popup select enhancement')
}

const GRADIENT_SURFACE_RE = /(?:library-ingest|profile-identity|mic-record-modal|stat-card)\b/
for (const file of files) {
  const text = await readFile(file, 'utf8')
  if (text.includes('ring-sky-')) {
    issues.push(`${rel(file)}: legacy ring-sky-* — use neutral dashboard gradient (from-primary/5)`)
  }
  if (text.includes('bg-[#fafcfe]')) {
    issues.push(`${rel(file)}: hard-coded ingest tint — use bg-gradient-to-t from-primary/5 to-card`)
  }
  if (GRADIENT_SURFACE_RE.test(text) && (!text.includes('bg-gradient-to-t') || !text.includes('from-primary/5'))) {
    issues.push(
      `${rel(file)}: dashboard gradient surfaces need bg-gradient-to-t and from-primary/5 (see StatCard / library ingest)`,
    )
  }
}

if (issues.length) {
  console.error('UI migration check failed:\n')
  for (const msg of issues) console.error(`  • ${msg}`)
  process.exit(1)
}

console.log(`UI migration check OK (${legacyBadgeCount} legacy badge class refs, cap ${MAX_LEGACY_BADGE})`)
