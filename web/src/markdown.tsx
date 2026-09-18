import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

const FENCE = /^```(?:markdown|md)?\r?\n([\s\S]*?)\r?\n```$/

export function unwrapMarkdownFence(text: string): string {
  const trimmed = text.trim()
  const match = trimmed.match(FENCE)
  if (match) return match[1]
  const openFence = trimmed.match(/^```(?:markdown|md)?\r?\n([\s\S]*)$/)
  if (openFence) return openFence[1].trimEnd()
  return text
}

export function MarkdownBody({ text }: { text: string }) {
  return (
    <div className="summary-md">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{unwrapMarkdownFence(text)}</ReactMarkdown>
    </div>
  )
}

export function downloadMarkdown(text: string, filename: string): void {
  const body = unwrapMarkdownFence(text)
  const blob = new Blob([body], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename.endsWith('.md') ? filename : `${filename}.md`
  link.click()
  URL.revokeObjectURL(url)
}
