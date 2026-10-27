import { useState } from 'react';
import { Button } from '@/components/atoms/Button';
import { Input } from '@/components/atoms/Input';
import { Notice } from '@/components/atoms/Notice';
import { Switch } from '@/components/atoms/Switch';
import { ChoiceChips } from '@/components/molecules/ChoiceChips';
import { ConfirmButton } from '@/components/molecules/ConfirmButton';
import { DayPicker } from '@/components/molecules/DayPicker';
import { Field } from '@/components/molecules/Field';
import { Sheet } from '@/components/templates/Sheet';
import { api } from '@/api/endpoints';
import type { RuleCreate, RuleKind, ScheduleRule } from '@/api/types';
import { useDeviceAction } from '@/hooks/useDevice';
import { errorMessage } from '@/lib/errors';
import { draftFromRule, draftProblem, draftToRule, INTERVAL_HOURS, ruleLabel, type RuleDraft } from '@/lib/schedule';

export interface RuleSheetProps {
  open: boolean;
  deviceId: string;
  /** The rule to edit, or null to add one. */
  rule: ScheduleRule | null;
  timeZone: string;
  onClose: () => void;
}

const KINDS: readonly { value: RuleKind; label: string }[] = [
  { value: 'daily', label: 'Daily' },
  { value: 'weekly', label: 'Weekly' },
  { value: 'interval', label: 'Every…' },
  { value: 'once', label: 'Once' },
];

/** Add or edit one schedule time: kind, days or interval, date and time in the home zone, double dose. */
export function RuleSheet({ open, deviceId, rule, timeZone, onClose }: RuleSheetProps) {
  return (
    <Sheet open={open} onClose={onClose} title={rule ? 'Edit time' : 'Add a time'}>
      {open && <RuleForm deviceId={deviceId} rule={rule} timeZone={timeZone} onDone={onClose} />}
    </Sheet>
  );
}

function RuleForm({ deviceId, rule, timeZone, onDone }: Omit<RuleSheetProps, 'open' | 'onClose'> & { onDone: () => void }) {
  const [draft, setDraft] = useState(() => draftFromRule(rule, timeZone));
  const save = useDeviceAction(deviceId, (body: RuleCreate) => (rule ? api.updateRule(rule.id, body) : api.createRule(deviceId, body)));
  const remove = useDeviceAction(deviceId, (ruleId: number) => api.deleteRule(ruleId));
  const set = (changes: Partial<RuleDraft>) => setDraft({ ...draft, ...changes });
  const problem = draftProblem(draft);
  const dated = draft.kind === 'once' || draft.kind === 'interval';
  const busy = save.isPending || remove.isPending;
  const failure = save.error ?? remove.error;

  return (
    <div className="flex flex-col gap-4">
      <ChoiceChips label="Repeats" className="grid grid-cols-4" options={KINDS} selected={draft.kind} onSelect={(kind) => set({ kind })} />
      {draft.kind === 'weekly' && <DayPicker mask={draft.daysMask} onChange={(daysMask) => set({ daysMask })} />}
      {draft.kind === 'interval' && (
        <Field label="Every how many hours" hint={`${INTERVAL_HOURS.min} to ${INTERVAL_HOURS.max} hours`}>
          <Input
            type="number"
            inputMode="numeric"
            min={INTERVAL_HOURS.min}
            max={INTERVAL_HOURS.max}
            value={Number.isNaN(draft.intervalHours) ? '' : draft.intervalHours}
            onChange={(event) => set({ intervalHours: event.target.valueAsNumber })}
          />
        </Field>
      )}
      <div className="grid grid-cols-2 gap-3">
        {dated && (
          <Field label={draft.kind === 'once' ? 'Date' : 'First dose'}>
            <Input type="date" value={draft.date} onChange={(event) => set({ date: event.target.value })} />
          </Field>
        )}
        <Field label="Time">
          <Input type="time" value={draft.time} onChange={(event) => set({ time: event.target.value })} />
        </Field>
      </div>
      <div className="flex items-center gap-3">
        <div className="min-w-0 flex-1">
          <p className="m-0 font-medium">Double dose</p>
          <p className="m-0 text-sm text-dim">Dispense two doses at this time.</p>
        </div>
        <Switch label="Double dose" checked={draft.doubleDose} onChange={(doubleDose) => set({ doubleDose })} />
      </div>
      <Notice tone={problem ? 'warn' : 'neutral'} className="font-medium text-fg">
        {problem ?? ruleLabel(draftToRule(draft, timeZone), timeZone)}
      </Notice>
      {failure && <Notice tone="bad" role="alert">{errorMessage(failure)}</Notice>}
      <Button
        variant="primary"
        className="min-h-[50px]"
        disabled={problem !== null || busy}
        onClick={() => save.mutate(draftToRule(draft, timeZone), { onSuccess: onDone })}
      >
        Save
      </Button>
      {rule && (
        <ConfirmButton
          label="Delete this time"
          armedLabel="Tap again to delete"
          disabled={busy}
          onConfirm={() => remove.mutate(rule.id, { onSuccess: onDone })}
        />
      )}
    </div>
  );
}
