import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

const FENCE = /^```(?:markdown|md)?\r?\n([\s\S]*?)\r?\n```$/

export function unwrapMarkdownFence(text: string): string {
  const trimmed = text.trim()
  const match = trimmed.match(FENCE)
  return match ? match[1] : text
}

export function MarkdownBody({ text }: { text: string }) {
  return (
    <div className="summary-md">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{unwrapMarkdownFence(text)}</ReactMarkdown>
    </div>
  )
}
