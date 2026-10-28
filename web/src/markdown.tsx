import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { Components } from 'react-markdown'

const FENCE = /^```(?:markdown|md)?\r?\n([\s\S]*?)\r?\n```$/

export function unwrapMarkdownFence(text: string): string {
  const trimmed = text.trim()
  const match = trimmed.match(FENCE)
  if (match) return match[1]
  const openFence = trimmed.match(/^```(?:markdown|md)?\r?\n([\s\S]*)$/)
  if (openFence) return openFence[1].trimEnd()
  return text
}

const markdownComponents: Components = {
  table: ({ node: _node, children, ...props }) => (
    <div className="typeset-scroll">
      <table {...props}>{children}</table>
    </div>
  ),
}

export function MarkdownBody({ text }: { text: string }) {
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
      {unwrapMarkdownFence(text)}
    </ReactMarkdown>
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
