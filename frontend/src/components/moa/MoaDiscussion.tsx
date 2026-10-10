import GroupChat from './GroupChat'
import PlanDisplay from './PlanDisplay'
import type { GroupMsg, GroupPlan, GroupContext } from '../../hooks/useGroupChat'

interface Props {
  messages: GroupMsg[]
  plan: GroupPlan | null
  tempPlan: Record<string, string[]> | null
  planConfirmed: boolean
  loading: boolean
  error: string | null
  ctx: GroupContext
  onSend: (text: string) => void
  onExportWord: () => void
  exporting: boolean
  awaitingUser?: null | { kind: 'user' | 'confirm'; prompt: string }
  onResume?: (text: string) => void
}

export default function MoaDiscussion({
  messages, plan, tempPlan, planConfirmed, loading, error, ctx, onSend, onExportWord, exporting, awaitingUser, onResume,
}: Props) {
  return (
    <div className="flex-1 flex min-w-0 min-h-0 h-full">
      <div className="flex-1 min-w-0">
        <GroupChat
          messages={messages}
          loading={loading}
          error={error}
          ctx={ctx}
          onSend={onSend}
          awaitingUser={awaitingUser}
          onResume={onResume}
        />
      </div>
      <div className="w-[480px] shrink-0">
        <PlanDisplay plan={plan} tempPlan={tempPlan} planConfirmed={planConfirmed} ctx={ctx} exporting={exporting} onExportWord={onExportWord} />
      </div>
    </div>
  )
}
