import { describe, expect, it } from 'vitest'
import {
  DEFAULT_LIST_PAGE_SIZE,
  LIST_PAGE_SIZE_OPTIONS,
  LIST_PAGE_SIZES,
  listPageBounds,
} from './selectOptions'

describe('listPageBounds', () => {
  it('clamps page to last index', () => {
    expect(listPageBounds(25, 99, 10)).toEqual({
      pageCount: 3,
      safePage: 2,
      offset: 20,
    })
  })

  it('uses page 0 when total is empty', () => {
    expect(listPageBounds(0, 3, 10)).toEqual({
      pageCount: 1,
      safePage: 0,
      offset: 0,
    })
  })

  it('computes offset for middle page', () => {
    expect(listPageBounds(100, 2, 10)).toEqual({
      pageCount: 10,
      safePage: 2,
      offset: 20,
    })
  })

  it('treats exact multiple of page size as full last page', () => {
    expect(listPageBounds(20, 1, 10)).toEqual({
      pageCount: 2,
      safePage: 1,
      offset: 10,
    })
  })
})

describe('list page size constants', () => {
  it('defaults to 10 and matches option values', () => {
    expect(DEFAULT_LIST_PAGE_SIZE).toBe(10)
    expect(LIST_PAGE_SIZE_OPTIONS.map((o) => Number(o.value))).toEqual([...LIST_PAGE_SIZES])
  })
})
