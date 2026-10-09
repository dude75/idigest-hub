import { useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '../../api'
import { AdminFormCard, AdminPage } from '../../components/AdminSection'
import { AdminFormActions, AppSubmitButton, HubBadge } from '../../components/app/AdminUi'
import { AppListPagination } from '../../components/app/AppListPagination'
import { ListSection } from '../../components/app/EntityUi'
import { ListRow } from '../../components/ListRow'
import { StatCard, StatGrid } from '../../components/StatCard'
import type { SchemaSkillListResponse } from '../../openapi'
import { fmtDate, formatInteger, showError } from '../../util'
import { Button } from '@/components/ui/button'
import { AppInputField } from '../../components/app/AppFormControls'
import {
  DEFAULT_LIST_PAGE_SIZE,
  listPageBounds,
  type ListPageSize,
} from '../../components/app/selectOptions'
import { AppField } from '../../components/app/AppField'

export function InstanceBaseSkillsTab() {
  const { t } = useTranslation()
  const [skills, setSkills] = useState<NonNullable<SchemaSkillListResponse['items']>>([])
  const [sname, setSname] = useState('')
  const [sbody, setSbody] = useState('')
  const [formOpen, setFormOpen] = useState(false)
  const [saveBusy, setSaveBusy] = useState(false)
  const [pageSize, setPageSize] = useState<ListPageSize>(DEFAULT_LIST_PAGE_SIZE)
  const [page, setPage] = useState(0)
  const formRef = useRef<HTMLDivElement>(null)

  const sortedSkills = useMemo(
    () => [...skills].sort((a, b) => b.created_at.localeCompare(a.created_at)),
    [skills],
  )

  const listTotal = sortedSkills.length
  const { safePage, offset } = listPageBounds(listTotal, page, pageSize)
  const pagedSkills = sortedSkills.slice(offset, offset + pageSize)

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
          <Button type="button" size="sm" onClick={openCreate}>
            {t('instance.baseSkillCreate')}
          </Button>
        }
        footer={
          listTotal > 0 ? (
            <AppListPagination
              htmlFor="base-skills-page-size"
              pageSize={pageSize}
              setPageSize={setPageSize}
              page={safePage}
              setPage={setPage}
              total={listTotal}
            />
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
