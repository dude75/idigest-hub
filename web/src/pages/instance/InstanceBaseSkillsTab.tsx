import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api } from '../../api'
import type { Skill } from '../../types'
import { fmtDate, showError } from '../../util'

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
    <>
      <div className="card stack">
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
      <div className="list">
        {skills.length === 0 && <p className="muted">{t('common.empty')}</p>}
        {skills.map((s) => (
          <div className="item row" key={s.id}>
            <div className="grow">
              <Link className="title" to={`/app/skill/${s.id}`}>{s.name}</Link>
              <div className="muted">{fmtDate(s.created_at)}</div>
            </div>
            <span className="badge">{s.scope}</span>
          </div>
        ))}
      </div>
    </>
  )
}
