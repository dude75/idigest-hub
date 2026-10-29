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

/** Tailwind data-variant or HubBadge tone map — not ad-hoc chrome copy. */
const ALLOW_TEXT_MUTED_FG = new Set([
  path.join(SRC, 'components/app/AdminUi.tsx'),
  path.join(SRC, 'components/app/AppDateField.tsx'),
])

/** Modal confirm — not a settings save row. */
const ALLOW_RAW_SUBMIT_BUTTON = new Set([
  path.join(SRC, 'pages/instance/WorkerImpactModal.tsx'),
  path.join(SRC, 'components/IngestExtraTagsMultiSelect.tsx'),
  path.join(SRC, 'pages/profile/ProfileSection.tsx'),
])

/** Legacy `.badge` in className — use HubBadge. */
const MAX_LEGACY_BADGE = 0

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
      !stackClass[1].includes('shell-global-mic-stack')
    ) {
      issues.push(
        `${rel(file)}:${i + 1}: legacy "stack" layout — use appFormStack / appSharePanelStack from appTypography`,
      )
    }
    if (
      stackClass &&
      /(?:^|\s)row(?:\s|$)/.test(stackClass[1]) &&
      !stackClass[1].includes('check-row') &&
      !stackClass[1].includes('share-picker-row') &&
      !stackClass[1].includes('AppCheckboxRow') &&
      !stackClass[1].includes('flex-row') &&
      !file.includes('check-ui-migration')
    ) {
      issues.push(
        `${rel(file)}:${i + 1}: legacy "row" layout — use flex flex-wrap items-center gap-2`,
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
    if (/<Link\b[^>]*className=["']title\b/.test(line)) {
      issues.push(
        `${rel(file)}:${i + 1}: legacy Link class "title" — use appListRowTitle from appTypography`,
      )
    }
    if (/className=["'][^"']*(?:^|\s)muted(?:\s|$)/.test(line) && !file.includes('check-ui-migration')) {
      issues.push(
        `${rel(file)}:${i + 1}: legacy "muted" class — use appMutedText / appMuted from appTypography`,
      )
    }
    if (
      !file.includes(`${path.sep}ui${path.sep}`) &&
      !file.endsWith('appTypography.ts') &&
      line.includes('text-sm text-muted-foreground') &&
      !file.includes('check-ui-migration')
    ) {
      issues.push(
        `${rel(file)}:${i + 1}: use appMutedText from appTypography instead of inline text-sm text-muted-foreground`,
      )
    }
    if (
      !file.includes(`${path.sep}ui${path.sep}`) &&
      !file.endsWith('appTypography.ts') &&
      !ALLOW_TEXT_MUTED_FG.has(file) &&
      line.includes('text-muted-foreground') &&
      !line.includes('data-[empty=true') &&
      !file.includes('check-ui-migration')
    ) {
      issues.push(
        `${rel(file)}:${i + 1}: use appMuted / appMutedText from appTypography instead of inline text-muted-foreground`,
      )
    }
    for (const legacyClass of [
      'entity-title',
      'stats-chart-title',
      'ingest-studio-card-title',
      'public-link-title',
      'entity-meta-row',
      'admin-lead',
      'share-field-label',
    ]) {
      if (line.includes(legacyClass) && !file.includes('check-ui-migration')) {
        issues.push(
          `${rel(file)}:${i + 1}: legacy "${legacyClass}" — use appTypography tokens or EntityPageTitle`,
        )
      }
    }
    if (line.includes('public-link-meta-item') && !file.includes('check-ui-migration')) {
      issues.push(`${rel(file)}:${i + 1}: use appMetaDl layout — not class "public-link-meta-item"`)
    }
    if (
      /className=["'][^"']*(?:^|\s)item(?:\s|$)/.test(line) &&
      !file.endsWith(`${path.sep}ListRow.tsx`) &&
      !file.includes('check-ui-migration')
    ) {
      issues.push(`${rel(file)}:${i + 1}: legacy "item" list class — use ListRow / listRowChrome`)
    }
    if (
      /className=["'][^"']*(?:^|\s)group(?:\s|$)/.test(line) &&
      !file.includes('check-ui-migration') &&
      !line.includes('RadioGroup') &&
      !line.includes('group/tabs') &&
      !line.includes('group-data') &&
      !line.includes('group-has-')
    ) {
      issues.push(`${rel(file)}:${i + 1}: legacy "group" container — use library-source-group or Tailwind`)
    }
    if (
      /\bpublic-link-meta\b(?!-item)/.test(line) &&
      !file.includes('check-ui-migration')
    ) {
      issues.push(
        `${rel(file)}:${i + 1}: legacy "public-link-meta" — use appMetaDl from appTypography`,
      )
    }
    if (/className=["'][^"']*\bitem-meta\b/.test(line) && !file.endsWith(`${path.sep}ListRow.tsx`)) {
      issues.push(
        `${rel(file)}:${i + 1}: legacy "item-meta" — use appListRowMeta via ListRow or appTypography`,
      )
    }
    if (/fmtMediaTime\(/.test(line) && !file.includes('AppDuration.tsx') && !file.includes('util.tsx') && !file.includes('StatsDaysView.tsx') && !file.includes('utteranceMedia.ts') && !file.includes('AudioPlayer.tsx') && !file.includes('MicrophoneRecordModal.tsx')) {
      issues.push(
        `${rel(file)}:${i + 1}: use AppDuration for UI durations — fmtMediaTime is for compact/chart/player helpers`,
      )
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
if (indexCss.includes('calc(14px * 1.05)')) {
  issues.push('index.css :root must use 16px Typeset base, not calc(14px * 1.05)')
}
if (!indexCss.includes('--hub-content-scale: 1.1')) {
  issues.push('index.css :root must define --hub-content-scale: 1.1 for app content width')
}
if (!indexCss.includes('max-width: var(--hub-page-max)')) {
  issues.push('index.css .page must use max-width: var(--hub-page-max)')
}
if (indexCss.includes('max-width: 1080px')) {
  issues.push('index.css: use var(--hub-page-max) instead of hard-coded 1080px')
}
if (!indexCss.includes('--hub-shell-max: var(--hub-page-max)')) {
  issues.push('index.css :root must set --hub-shell-max: var(--hub-page-max)')
}
if (!/\.entity-page-main\s*\{[^}]*display:\s*contents/.test(indexCss)) {
  issues.push('index.css .entity-page-main must use display: contents for entity back grid')
}
if (indexCss.includes('entity-back-offset')) {
  issues.push('index.css must not use JS entity-back-offset — use entity-page grid')
}
if (!/\.entity-page-layout:has\([\s\S]*?\)\s*\.entity-back/.test(indexCss)) {
  issues.push('index.css must align entity back on row 2 when a title precedes cards')
}
if (!indexCss.includes('--font-sans: var(--font-geist)')) {
  issues.push('index.css :root must define --font-sans from Geist')
}
if (!indexCss.includes('--font-mono: var(--font-geist-mono)')) {
  issues.push('index.css :root must define --font-mono from Geist Mono')
}
if (/\bInter,/.test(indexCss)) {
  issues.push('index.css must not reference Inter — use --font-sans')
}
if (/font-family:\s*ui-monospace/.test(indexCss)) {
  issues.push('index.css: use var(--font-mono) instead of raw ui-monospace stacks')
}
if (indexCss.includes('.summary-md')) {
  issues.push('remove legacy .summary-md — use Typeset + hub-reading-surface')
}
if (indexCss.includes('.item a.title')) {
  issues.push('remove legacy .item a.title — use appListRowTitle in ListRow')
}
if (indexCss.includes('.item-meta')) {
  issues.push('remove legacy .item-meta — use appListRowMeta in ListRow')
}
if (indexCss.includes('.entity-title')) {
  issues.push('remove legacy .entity-title — use EntityPageTitle / appEntityTitle')
}
if (indexCss.includes('.stats-chart-title')) {
  issues.push('remove legacy .stats-chart-title — use appChartEyebrow')
}
if (indexCss.includes('.public-link-title')) {
  issues.push('remove legacy .public-link-title — use appListRowTitle')
}
if (/\.muted\s*\{/.test(indexCss)) {
  issues.push('remove legacy .muted rule from index.css — use appTypography tokens')
}
if (/hub-muted/.test(indexCss)) {
  issues.push('index.css must not use --hub-muted — use var(--muted-foreground) or appTypography in TSX')
}
if (/\.admin-lead\s*\{[^}]*color:\s*var\(--muted-foreground\)/.test(indexCss)) {
  issues.push('remove legacy .admin-lead typography — use appAdminLead / appProfileSectionLead')
}
if (/\.share-field-label\s*\{[^}]*font-size:/.test(indexCss)) {
  issues.push('remove legacy .share-field-label typography — use appFieldCaption')
}
if (/\.row\s*\{/.test(indexCss)) {
  issues.push('remove legacy .row rule from index.css — use Tailwind flex utilities')
}
if (/\.stack\s*\{/.test(indexCss)) {
  issues.push('remove legacy .stack rule from index.css — use appFormStack from appTypography')
}
if (/\.grow\s*\{/.test(indexCss)) {
  issues.push('remove legacy .grow rule from index.css — use Tailwind grow utility')
}
if (/\.share-panel\s*\{[^}]*#f8fafc/.test(indexCss)) {
  issues.push('share-panel must use --share-panel-bg / appSharePanelSurface, not #f8fafc')
}
if (/\.landing-pricing-btn\s*\{[^}]*font-size:/.test(indexCss)) {
  issues.push('landing-pricing-btn typography — use appLandingPricingBtn from appTypography')
}
if (!indexCss.includes('--share-panel-bg:')) {
  issues.push('index.css :root must define --share-panel-bg for share panels')
}
if (/\.item\s*\{/.test(indexCss)) {
  issues.push('remove legacy .item rule — use listRowChrome on ListRow ([data-slot=list-row])')
}
if (/\.group\s*\{/.test(indexCss)) {
  issues.push('rename legacy .group containers — use .library-source-group')
}
if (indexCss.includes('.public-link-meta-item')) {
  issues.push('remove .public-link-meta-item — use flex wrappers + appMetaDl')
}
if (indexCss.includes('.tariff-rates-line') || indexCss.includes('.audit-payload')) {
  issues.push('remove dead tariff-rates / audit-payload CSS')
}
if (
  !/\.hub-reading-surface,\s*\n\s*\.summary-body,\s*\n\s*\.agreement-text/.test(indexCss)
) {
  issues.push('index.css must unify reading typography on hub-reading-surface, summary-body, agreement-text')
}
const typesetCss = await readFile(path.join(SRC, 'typeset.css'), 'utf8')
if (
  !/\.typeset :where\(\.hub-reading-surface, \.summary-body, \.agreement-text\) :where\(ul\)/.test(
    typesetCss,
  )
) {
  issues.push('typeset.css must scope ul/ol/li prose to reading surfaces only')
}
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
if (!authShell.includes('--muted-foreground:')) {
  issues.push('auth-shell.css :root must define --muted-foreground aligned with SPA')
}
if (!/\.muted\s*\{[^}]*font-size:\s*0\.875rem/.test(authShell)) {
  issues.push('auth-shell.css .muted must use 0.875rem (appMutedText) for OAuth copy')
}
try {
  await access(path.join(import.meta.dirname, '../public/auth-shell.js'))
} catch {
  issues.push('missing web/public/auth-shell.js — OAuth popup select enhancement')
}

/** Library ingest uses flat card + shadow; gradient required on stat/profile/mic surfaces only. */
const GRADIENT_SURFACE_RE = /(?:profile-identity|mic-record-modal|stat-card)\b/
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

for (const file of files) {
  if (!file.endsWith('.test.tsx')) continue
  const text = await readFile(file, 'utf8')
  if (!/from ['"]react-i18next['"]/.test(text)) continue
  if (!/\brender\s*\(/.test(text)) continue
  if (text.includes('@/test/render') || text.includes('renderWithI18n') || text.includes('renderWithRouter')) {
    continue
  }
  issues.push(
    `${rel(file)}: components with useTranslation in tests must use renderWithI18n/renderWithRouter from @/test/render`,
  )
}

if (issues.length) {
  console.error('UI migration check failed:\n')
  for (const msg of issues) console.error(`  • ${msg}`)
  process.exit(1)
}

console.log(`UI migration check OK (${legacyBadgeCount} legacy badge class refs, cap ${MAX_LEGACY_BADGE})`)
