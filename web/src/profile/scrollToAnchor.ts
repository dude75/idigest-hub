/** Scroll to a profile hash target after layout (sticky topbar). */
export function scrollToProfileAnchor(anchorId: string, behavior: ScrollBehavior = 'smooth') {
  document.getElementById(anchorId)?.scrollIntoView({ behavior, block: 'start' })
}
