import type { ActionState, GoalState, LinkType, MeetingCategory, Priority, Role } from './types'

export const ROLE: Record<Role, string> = { advisor: '指導者', student: '學生' }

export const GOAL_STATE: Record<GoalState, string> = {
  planned: '規劃中',
  investigating: '研究中',
  partially_answered: '部分回答',
  answered: '已回答',
  needs_revisit: '需重新檢視',
  archived: '已封存',
}

export const ACTION_STATE: Record<ActionState, string> = {
  open: '待處理',
  in_progress: '進行中',
  done: '已完成',
  canceled: '已取消',
}

export const PRIORITY: Record<Priority, string> = { high: '高', medium: '中', low: '低' }

export const CATEGORY: Record<MeetingCategory, string> = {
  lab: 'Lab Meeting',
  industry: '產學 Meeting',
  one_on_one: '個別 Meeting',
  other: '其他',
}

export const LINK_TYPE: Record<LinkType, string> = {
  general: '連結',
  experiment: '實驗紀錄',
  code: '程式碼 / Issue',
  document: '文件 / 簡報',
  data: '資料',
}

export const EVENT_KIND: Record<string, string> = {
  update: '進度',
  blocker: 'Blocker',
  decision: 'Meeting 決策',
  action: '待辦',
  goal: '目標',
}

export function eventKind(eventType: string): string {
  if (eventType.startsWith('update')) return 'update'
  if (eventType.startsWith('blocker')) return 'blocker'
  if (eventType.startsWith('outcome') || eventType.startsWith('meeting')) return 'decision'
  if (eventType.startsWith('action')) return 'action'
  if (eventType.startsWith('goal')) return 'goal'
  return 'other'
}
