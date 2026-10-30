/**
 * Shared legacy UI guards for check-ui-migration.mjs and vitest (legacyUiGuard.test.ts).
 */

/** Legacy `.badge` in TSX className — use HubBadge. */
export const MAX_LEGACY_BADGE = 0

export function hasLegacyCardToken(classFragment) {
  return /(?:^|\s)card(?:\s|$)/.test(classFragment)
}

export function hasLegacyBtnToken(classFragment) {
  return /(?:^|\s)btn(?:\s|$)/.test(classFragment)
}

export function countLegacyBadgeInLine(line) {
  return (line.match(/className=["'][^"']*\bbadge\b/g) || []).length
}

export function countLegacyBadgeInTsx(text) {
  let total = 0
  for (const line of text.split('\n')) {
    total += countLegacyBadgeInLine(line)
  }
  return total
}

/** Legacy global class tokens scanned in TSX (see check-ui-migration.mjs). */
export const LEGACY_TSX_CLASS_NAMES = [
  'entity-title',
  'stats-chart-title',
  'ingest-studio-card-title',
  'public-link-title',
  'entity-meta-row',
  'admin-lead',
  'share-field-label',
  'public-link-meta-item',
  'public-link-meta',
  'item-meta',
  'stats-table',
  'sso-url-copy',
  'public-link-copy',
]

export function lineUsesLegacyTsxClassName(line, legacyClass) {
  if (legacyClass === 'item-meta') {
    return /className=["'][^"']*\bitem-meta\b/.test(line)
  }
  if (legacyClass === 'public-link-meta') {
    return /\bpublic-link-meta\b(?!-item)/.test(line)
  }
  return line.includes(legacyClass)
}

export function lineUsesLegacyMutedClass(line) {
  const m = line.match(/className=["']([^"']+)["']/)
  if (!m) return false
  return /(?:^|\s)muted(?:\s|$)/.test(m[1])
}

export function lineUsesLegacyStackClass(line) {
  const stackClass = line.match(/className=["']([^"']+)["']/)
  if (!stackClass) return false
  return (
    /(?:^|\s)stack(?:\s|$)/.test(stackClass[1]) && !stackClass[1].includes('shell-global-mic-stack')
  )
}

export function lineUsesLegacyRowClass(line) {
  const stackClass = line.match(/className=["']([^"']+)["']/)
  if (!stackClass) return false
  return (
    /(?:^|\s)row(?:\s|$)/.test(stackClass[1]) &&
    !stackClass[1].includes('check-row') &&
    !stackClass[1].includes('share-picker-row') &&
    !stackClass[1].includes('AppCheckboxRow') &&
    !stackClass[1].includes('flex-row')
  )
}

/** @param {string} indexCss */
export function validateIndexCss(indexCss) {
  const issues = []
  if (indexCss.includes('calc(14px * 1.05)')) {
    issues.push('index.css :root must use 16px Typeset base, not calc(14px * 1.05)')
  }
  if (!indexCss.includes('--hub-content-scale: 1;')) {
    issues.push('index.css :root must define --hub-content-scale: 1 for app content width')
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
  if (!indexCss.includes('--landing-popular-accent:')) {
    issues.push('index.css :root must define --landing-popular-accent for pricing cards')
  }
  if (/\.btn\s*\{/.test(indexCss)) {
    issues.push('remove legacy .btn class rules from index.css — SPA uses shadcn Button; OAuth uses auth-shell.css')
  }
  if (/\.landing-pricing-popular\s*\{/.test(indexCss)) {
    issues.push('remove .landing-pricing-popular — use appLandingPopularBadge')
  }
  if (/\.worker-impact-pair\s*\{/.test(indexCss)) {
    issues.push('remove .worker-impact-pair typography — use appImpactPairMono')
  }
  if (/\.ingest-studio-card\s*\{[^}]*background:/.test(indexCss)) {
    issues.push('ingest studio card chrome must use ingestStudioCardChrome token, not CSS background')
  }
  if (/\.item\s*\{/.test(indexCss)) {
    issues.push('remove legacy .item rule — use ListRow with listRowLayout ([data-slot=list-row])')
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
    issues.push(
      'index.css must unify reading typography on hub-reading-surface, summary-body, agreement-text',
    )
  }
  return issues
}

/** @param {string} listRowTsx */
export function validateListRowTsx(listRowTsx) {
  const issues = []
  if (listRowTsx.includes('listRowChrome')) {
    issues.push(
      'ListRow must use listRowLayout on [data-slot=list-row] — listRowChrome doubles Card corner radius in embedded lists',
    )
  }
  return issues
}

/** Remaining index.css globals to delete in a later pass (still referenced or historical). */
export const INDEX_CSS_LEGACY_GLOBALS_TODO = ['.card {', '.tabs {', '.badge {']

/** @param {string} typesetCss */
export function validateTypesetCss(typesetCss) {
  const issues = []
  if (
    !/\.typeset :where\(\.hub-reading-surface, \.summary-body, \.agreement-text\) :where\(ul\)/.test(
      typesetCss,
    )
  ) {
    issues.push('typeset.css must scope ul/ol/li prose to reading surfaces only')
  }
  return issues
}
