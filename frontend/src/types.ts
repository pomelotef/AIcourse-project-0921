export type Role = 'advisor' | 'student'
export type GoalState = 'planned' | 'investigating' | 'partially_answered' | 'answered' | 'needs_revisit' | 'archived'
export type ActionState = 'open' | 'in_progress' | 'done' | 'canceled'
export type Priority = 'high' | 'medium' | 'low'
export type MeetingCategory = 'lab' | 'industry' | 'one_on_one' | 'other'
export type LinkType = 'general' | 'experiment' | 'code' | 'document' | 'data'

export interface UserRef { id: number; name: string }
export interface Me extends UserRef { email: string }
export interface Member extends UserRef { email: string; role: Role }
export interface Ref { id: number; title: string }

export interface Project {
  id: number
  title: string
  description: string
  state: 'active' | 'archived'
  my_role: Role
  members: Member[]
}

export interface Link { id: number; url: string; label: string; link_type: LinkType }

export interface Goal {
  id: number
  project_id: number
  parent_id: number | null
  title: string
  research_question: string
  assignee: UserRef | null
  research_state: GoalState
  visibility: 'shared' | 'private'
  created_by: UserRef
  updated_at: string
  open_blocker_count?: number
  open_action_count?: number
  last_update_at?: string | null
  project_title?: string
}

export interface BlockerRef { id: number; title: string; state: 'open' | 'resolved' }

export interface Update {
  id: number
  project_id: number
  goal: Ref | null
  author: UserRef
  completed: string
  findings: string
  next_steps: string
  no_blocker: boolean
  draft_blockers: { title: string; description: string }[]
  blockers: BlockerRef[]
  publication_state: 'draft' | 'published'
  created_at: string
  updated_at: string
  published_at: string | null
  links: Link[]
}

export interface Blocker {
  id: number
  project_id: number
  goal: Ref | null
  reported_by: UserRef
  title: string
  description: string
  state: 'open' | 'resolved'
  opened_at: string
  resolved_at: string | null
  resolved_by: UserRef | null
  resolution: string
  reference_count: number
}

export interface MeetingRef { id: number; title: string; category: MeetingCategory; occurred_at: string }

export interface Action {
  id: number
  project_id: number
  goal: Ref | null
  source_meeting: MeetingRef | null
  title: string
  assignee: UserRef
  priority: Priority
  state: ActionState
  due_date: string | null
  note: string
  created_by: UserRef
  created_at: string
  overdue?: boolean
}

export interface Meeting {
  id: number
  project_id: number
  title: string
  category: MeetingCategory
  occurred_at: string
  agenda: string
  participants: UserRef[]
  created_by: UserRef
  outcome_count?: number
  pending_outcome_count?: number
  project_title?: string
}

export interface Outcome {
  id: number
  meeting: MeetingRef
  goal: Ref | null
  decision: string
  rationale: string
  feedback: string
  author: UserRef
  confirmation_state: 'pending' | 'confirmed'
  confirmed_by: UserRef | null
  confirmed_at: string | null
  created_at: string
  comments: { id: number; author: UserRef; body: string; created_at: string }[]
}

export interface TimelineEvent {
  id: number
  goal: Ref | null
  actor: UserRef
  event_type: string
  entity_type: string
  entity_id: number
  summary: string
  meeting_category: MeetingCategory | null
  private: boolean
  created_at: string
}

export interface Note { id: number; body: string; updated_at: string }
