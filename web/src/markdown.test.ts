import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { createElement } from 'react'
import { MarkdownBody, unwrapMarkdownFence } from './markdown'

describe('unwrapMarkdownFence', () => {
  it('unwraps a full markdown fence', () => {
    const input = '```markdown\n# Title\n\nBody\n```'
    expect(unwrapMarkdownFence(input)).toBe('# Title\n\nBody')
  })

  it('unwraps an opening fence without closing fence', () => {
    const input = '```markdown\n# Title\n\n| A | B |\n|---|---|'
    expect(unwrapMarkdownFence(input)).toBe('# Title\n\n| A | B |\n|---|---|')
  })

  it('leaves plain markdown unchanged', () => {
    const input = '# Title\n\nParagraph'
    expect(unwrapMarkdownFence(input)).toBe(input)
  })
})

describe('MarkdownBody', () => {
  it('renders markdown headings and tables', () => {
    const text = `# User Agreement

- item one

| Topic | Rule |
| --- | --- |
| Uploads | rights required |`
    const html = renderToStaticMarkup(createElement(MarkdownBody, { text }))
    expect(html).toContain('<h1>')
    expect(html).toContain('<table>')
    expect(html).toContain('Uploads')
  })
})
