import { useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '../../api'
import { AdminFormCard, AdminPage } from '../../components/AdminSection'
import { AdminFormActions, AppSubmitButton, HubBadge } from '../../components/app/AdminUi'
import { AdminTablePager } from '../../components/app/AdminDataTable'
import { ListSection } from '../../components/app/EntityUi'
import { ListRow } from '../../components/ListRow'
import { StatCard, StatGrid } from '../../components/StatCard'
import type { SchemaSkillListResponse } from '../../openapi'
import { fmtDate, formatInteger, showError } from '../../util'
import { Button } from '@/components/ui/button'
import { AppInputField, AppPageSizeField } from '../../components/app/AppFormControls'
import { pageSizeOptions } from '../../components/app/selectOptions'
import { AppField } from '../../components/app/AppField'

const PAGE_SIZES = [10, 50, 100] as const
type PageSize = (typeof PAGE_SIZES)[number]

export function InstanceBaseSkillsTab() {
  const { t } = useTranslation()
  const [skills, setSkills] = useState<NonNullable<SchemaSkillListResponse['items']>>([])
  const [sname, setSname] = useState('')
  const [sbody, setSbody] = useState('')
  const [formOpen, setFormOpen] = useState(false)
  const [saveBusy, setSaveBusy] = useState(false)
  const [pageSize, setPageSize] = useState<PageSize>(10)
  const [page, setPage] = useState(0)
  const formRef = useRef<HTMLDivElement>(null)

  const sortedSkills = useMemo(
    () => [...skills].sort((a, b) => b.created_at.localeCompare(a.created_at)),
    [skills],
  )

  const listTotal = sortedSkills.length
  const pageCount = Math.max(1, Math.ceil(listTotal / pageSize))
  const safePage = Math.min(page, pageCount - 1)
  const listFrom = listTotal === 0 ? 0 : safePage * pageSize + 1
  const listTo = Math.min(listTotal, (safePage + 1) * pageSize)
  const pagedSkills = sortedSkills.slice(safePage * pageSize, safePage * pageSize + pageSize)

  async function load() {
    try {
      setSkills((await api<SchemaSkillListResponse>('/skills/base')).items ?? [])
    } catch (e) {
      showError(e)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  function scrollToForm() {
    requestAnimationFrame(() => formRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
  }

  function openCreate() {
    setSname('')
    setSbody('')
    setFormOpen(true)
    scrollToForm()
  }

  function cancelCreate() {
    setSname('')
    setSbody('')
    setFormOpen(false)
  }

  async function saveSkill() {
    setSaveBusy(true)
    try {
      await api('/skills/base', { method: 'POST', body: JSON.stringify({ name: sname, body: sbody }) })
      cancelCreate()
      await load()
    } catch (e) {
      showError(e)
    } finally {
      setSaveBusy(false)
    }
  }

  const pageSizeSelect = (
    <AppPageSizeField
      label={t('task.pageSize')}
      htmlFor="base-skills-page-size"
      value={String(pageSize)}
      onValueChange={(v) => {
        setPageSize(Number(v) as PageSize)
        setPage(0)
      }}
      options={pageSizeOptions(PAGE_SIZES)}
    />
  )

  return (
    <AdminPage>
      <StatGrid>
        <StatCard label={t('instance.baseSkillsTotal')} value={formatInteger(skills.length)} tone="ops" />
      </StatGrid>

      {formOpen ? (
        <div ref={formRef}>
          <AdminFormCard title={t('instance.baseSkillCreate')}>
            <AppInputField
              label={t('common.name')}
              htmlFor="base-skill-name"
              value={sname}
              disabled={saveBusy}
              onChange={(e) => setSname(e.target.value)}
            />
            <AppField label={t('skills.body')} htmlFor="base-skill-body">
              <textarea
                id="base-skill-body"
                className="skill-editor"
                value={sbody}
                disabled={saveBusy}
                onChange={(e) => setSbody(e.target.value)}
              />
            </AppField>
            <AdminFormActions>
              <AppSubmitButton ready={Boolean(sname.trim())} busy={saveBusy} onClick={() => void saveSkill()}>
                {t('common.create')}
              </AppSubmitButton>
              <Button type="button" variant="outline" disabled={saveBusy} onClick={cancelCreate}>
                {t('common.cancel')}
              </Button>
            </AdminFormActions>
          </AdminFormCard>
        </div>
      ) : null}

      <ListSection
        title={t('instance.baseSkillsList')}
        empty={t('common.empty')}
        isEmpty={listTotal === 0}
        actions={
          <div className="flex flex-wrap items-end gap-3">
            <Button type="button" size="sm" onClick={openCreate}>
              {t('instance.baseSkillCreate')}
            </Button>
            {pageSizeSelect}
          </div>
        }
        footer={
          listTotal > pageSize ? (
            <AdminTablePager>
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={safePage === 0}
                onClick={() => setPage(safePage - 1)}
              >
                {t('common.prev')}
              </Button>
              <span className="text-sm text-muted-foreground">
                {t('task.pageRange', { from: listFrom, to: listTo, total: listTotal })}
              </span>
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={safePage >= pageCount - 1}
                onClick={() => setPage(safePage + 1)}
              >
                {t('common.next')}
              </Button>
            </AdminTablePager>
          ) : null
        }
      >
        {pagedSkills.map((s) => (
          <ListRow
            key={s.id}
            to={`/app/skill/${s.id}`}
            title={s.name}
            meta={fmtDate(s.created_at)}
            trailing={<HubBadge tone="muted">{s.scope}</HubBadge>}
          />
        ))}
      </ListSection>
    </AdminPage>
  )
}
