import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '../../api'
import { AdminPage, AdminTableCard } from '../../components/AdminSection'
import { ListRow } from '../../components/ListRow'
import { StatCard, StatGrid } from '../../components/StatCard'
import type { Skill } from '../../types'
import { fmtDate, formatInteger, showError } from '../../util'

export function InstanceBaseSkillsTab() {
  const { t } = useTranslation()
  const [skills, setSkills] = useState<Skill[]>([])
  const [sname, setSname] = useState('')
  const [sbody, setSbody] = useState('')

  async function load() {
    try {
      setSkills((await api<{ items: Skill[] }>('/skills/base')).items)
    } catch (e) {
      showError(e)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  return (
    <AdminPage>
      <StatGrid>
        <StatCard label={t('instance.baseSkillsTotal')} value={formatInteger(skills.length)} tone="ops" />
      </StatGrid>

      <details className="fold org-fold org-create-fold card">
        <summary className="org-fold-summary">
          <span>{t('instance.baseSkillCreate')}</span>
        </summary>
        <div className="stack fold-body">
          <label>{t('common.name')}<input value={sname} onChange={(e) => setSname(e.target.value)} /></label>
          <label>{t('skills.body')}<textarea className="skill-editor" value={sbody} onChange={(e) => setSbody(e.target.value)} /></label>
          <button
            className="primary"
            type="button"
            onClick={() =>
              void api('/skills/base', { method: 'POST', body: JSON.stringify({ name: sname, body: sbody }) }).then(() => {
                setSname('')
                setSbody('')
                return load()
              })
            }
          >
            {t('common.create')}
          </button>
        </div>
      </details>

      <AdminTableCard title={t('instance.baseSkillsList')} empty={t('common.empty')} isEmpty={skills.length === 0}>
        {skills.length > 0 ? (
          <div className="list admin-list">
            {skills.map((s) => (
              <ListRow
                key={s.id}
                to={`/app/skill/${s.id}`}
                title={s.name}
                meta={fmtDate(s.created_at)}
                trailing={<span className="badge">{s.scope}</span>}
              />
            ))}
          </div>
        ) : null}
      </AdminTableCard>
    </AdminPage>
  )
}
