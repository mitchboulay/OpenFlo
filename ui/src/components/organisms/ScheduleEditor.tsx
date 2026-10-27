import { useState } from 'react';
import { Badge } from '@/components/atoms/Badge';
import { Icon } from '@/components/atoms/Icon';
import { Notice } from '@/components/atoms/Notice';
import { Switch } from '@/components/atoms/Switch';
import { ListRow } from '@/components/molecules/ListRow';
import { PendingBadge } from '@/components/molecules/PendingBadge';
import { SectionCard } from '@/components/molecules/SectionCard';
import { api } from '@/api/endpoints';
import type { DeviceDetail, Schedule, ScheduleRule } from '@/api/types';
import { useDeviceAction, useSchedule } from '@/hooks/useDevice';
import { errorMessage } from '@/lib/errors';
import { entryStatus, ruleLabel } from '@/lib/schedule';
import { formatDateTime, zoneLabel } from '@/lib/time';
import { QueryBoundary } from './QueryBoundary';
import { RuleSheet } from './RuleSheet';
import { ScheduleIntroSheet } from './ScheduleIntroSheet';

export interface ScheduleEditorProps {
  device: DeviceDetail;
  timeZone: string;
}

type OpenSheet = { kind: 'intro' } | { kind: 'rule'; rule: ScheduleRule | null } | null;

/** Why the server is withholding the schedule (AD-6: paused, flagged or retiring → nothing served). */
function pausedReason(device: DeviceDetail): string | null {
  if (device.retire_requested_at !== null) return 'Schedules have stopped while this device is being retired.';
  if (device.flags.some((flag) => flag.acked_at === null)) return 'Schedules are on hold until you review the warning above.';
  if (!device.controls.dispensing_enabled) return 'Schedules are paused while dispensing is off.';
  return null;
}

const ROW = 'flex min-h-12 w-full cursor-pointer items-center gap-3 px-3.5 py-3 text-left hover:bg-surface2';

/** FR-9: the Schedules switch, rules in plain language, and the next doses with where each one stands. */
export function ScheduleEditor({ device, timeZone }: ScheduleEditorProps) {
  const [sheet, setSheet] = useState<OpenSheet>(null);
  const schedule = useSchedule(device.device_id);
  const switchOff = useDeviceAction(device.device_id, () => api.updateControls(device.device_id, { schedules_enabled: false }));
  const on = device.controls.schedules_enabled;
  const paused = on ? pausedReason(device) : null;
  const close = () => setSheet(null);

  return (
    <SectionCard
      id="schedule"
      title="Schedule"
      icon="calendar"
      aside={
        <Switch
          label="Schedules"
          checked={on}
          disabled={device.status === 'retired' || switchOff.isPending}
          onChange={(next) => (next ? setSheet({ kind: 'intro' }) : switchOff.mutate())}
        />
      }
    >
      {switchOff.isError && <Notice tone="bad" role="alert">{errorMessage(switchOff.error)}</Notice>}
      {paused && (
        <Notice tone="warn" className="flex items-center gap-2.5">
          <Icon name="warning" size={18} className="flex-none text-warn" />
          {paused}
        </Notice>
      )}
      {on ? (
        <QueryBoundary query={schedule} what="the schedule">
          {(data) => (
            <>
              <RuleList rules={data.rules} timeZone={timeZone} onEdit={(rule) => setSheet({ kind: 'rule', rule })} />
              {!paused && <Upcoming entries={data.upcoming} device={device} timeZone={timeZone} />}
            </>
          )}
        </QueryBoundary>
      ) : (
        <p className="m-0 text-sm text-pretty text-dim">
          Schedules are off. Doses happen only when you tap Dispense now or press the device’s button.
        </p>
      )}
      <ScheduleIntroSheet open={sheet?.kind === 'intro'} device={device} rules={schedule.data?.rules ?? []} timeZone={timeZone} onClose={close} />
      <RuleSheet open={sheet?.kind === 'rule'} deviceId={device.device_id} rule={sheet?.kind === 'rule' ? sheet.rule : null} timeZone={timeZone} onClose={close} />
    </SectionCard>
  );
}

function RuleList({ rules, timeZone, onEdit }: { rules: Schedule['rules']; timeZone: string; onEdit: (rule: ScheduleRule | null) => void }) {
  return (
    <ul aria-label="Times" className="m-0 list-none overflow-hidden rounded-button border border-border p-0">
      {rules.map((rule) => (
        <li key={rule.id} className="border-t border-border first:border-t-0">
          <button type="button" className={ROW} onClick={() => onEdit(rule)}>
            <Icon name="clock" size={18} className="flex-none text-dim" />
            <span className="min-w-0 flex-1 font-medium">{ruleLabel(rule, timeZone)}</span>
            <Icon name="chevron" size={18} className="flex-none text-faint" />
          </button>
        </li>
      ))}
      <li className="border-t border-border first:border-t-0">
        <button type="button" className={`${ROW} font-semibold text-accent-text`} onClick={() => onEdit(null)}>
          <Icon name="plus" size={18} className="flex-none" />
          Add a time
        </button>
      </li>
    </ul>
  );
}

function Upcoming({ entries, device, timeZone }: { entries: Schedule['upcoming']; device: DeviceDetail; timeZone: string }) {
  const zone = zoneLabel(timeZone, new Date(), 'shortGeneric');
  return (
    <div className="flex flex-col gap-1">
      <h3 className="m-0 text-[13px] font-semibold text-dim">Upcoming{zone ? ` · ${zone}` : ''}</h3>
      {entries.length === 0 ? (
        <p className="m-0 py-2 text-sm text-dim">Nothing coming up. Add a time above.</p>
      ) : (
        <ul className="m-0 list-none p-0">
          {entries.map((entry) => {
            const status = entryStatus(entry);
            return (
              <ListRow
                key={entry.id}
                variant="history"
                title={
                  <>
                    {formatDateTime(entry.at, timeZone)}
                    {entry.dose_count === 2 && <span className="font-normal text-dim"> · double dose</span>}
                  </>
                }
                value={
                  status ? <Badge tone={status.tone}>{status.label}</Badge> : <PendingBadge expectedAt={device.next_expected_sync} timeZone={timeZone} />
                }
              />
            );
          })}
        </ul>
      )}
    </div>
  );
}
