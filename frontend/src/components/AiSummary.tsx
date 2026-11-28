import { useState } from 'react'
import { api } from '../api'
import { useSubmit } from '../util'
import { Card, ErrorBox } from './ui'

type Kind = 'blocker' | 'decision_needed' | 'follow_up' | 'progress'
interface AiPoint { kind: Kind; text: string; record_ids: string[] }
interface AiSummaryResult {
  status: 'ok' | 'insufficient_data' | 'unavailable' | 'disabled'
  summary: string
  points: AiPoint[]
  records: Record<string, string>
}

const KIND_LABEL: Record<Kind, string> = {
  blocker: '阻礙', decision_needed: '需要決定', follow_up: '待追蹤', progress: '進度',
}

const STATUS_TEXT: Record<Exclude<AiSummaryResult['status'], 'ok'>, string> = {
  disabled: '伺服器沒有設定 AI 金鑰，AI 摘要目前沒有啟用。',
  insufficient_data: '這段期間的紀錄太少，無法產生摘要。',
  unavailable: 'AI 這次沒有產生可信的摘要，請直接參考下方的 Meeting Brief。',
}

/** AI pre-meeting summary. Generated only on click (each click is a paid model call). */
export function AiSummary({ meetingId, memberId }: { meetingId: number; memberId: number | '' }) {
  const [result, setResult] = useState<AiSummaryResult | null>(null)
  const { busy, error, run } = useSubmit()
  const url = `/api/meetings/${meetingId}/brief/ai-summary${memberId ? `?member_id=${memberId}` : ''}`
  const generate = () => void run(async () => setResult(await api.post<AiSummaryResult>(url)))

  return (
    <Card title="AI 會前摘要" className="ai-summary" actions={
      <button className="small" onClick={generate} disabled={busy}>
        {busy ? '產生中…' : result ? '重新產生' : '產生 AI 摘要'}
      </button>
    }>
      <p className="muted small">
        由 AI 依下方 Meeting Brief 的紀錄產生，只供會前參考；每一點都標出依據的紀錄，內容以原始紀錄為準。
      </p>
      <ErrorBox error={error} />
      {result && result.status !== 'ok' && <p className="empty">{STATUS_TEXT[result.status]}</p>}
      {result && result.status === 'ok' && (
        <>
          <p>{result.summary}</p>
          <ul className="ai-points">
            {result.points.map((p, i) => (
              <li key={i}>
                <span className={`badge ai-${p.kind}`}>{KIND_LABEL[p.kind]}</span> {p.text}
                <div className="muted small">
                  依據：{p.record_ids.map((rid) => result.records[rid] ?? rid).join('、')}
                </div>
              </li>
            ))}
          </ul>
        </>
      )}
    </Card>
  )
}
