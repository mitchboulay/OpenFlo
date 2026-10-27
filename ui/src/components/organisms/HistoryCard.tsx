import { useState } from 'react';
import { Button } from '@/components/atoms/Button';
import { Notice } from '@/components/atoms/Notice';
import { ListRow, type ListRowProps } from '@/components/molecules/ListRow';
import { SectionCard } from '@/components/molecules/SectionCard';
import { Tabs, tabPanelProps } from '@/components/molecules/Tabs';
import type { DispenseItem, EventItem, History, HistoryKind, SyncItem } from '@/api/types';
import { useDeviceHistory } from '@/hooks/useDevice';
import { useUnits } from '@/hooks/useUnits';
import { describeEventBatch, dispenseKind } from '@/lib/events';
import { formatDateTime } from '@/lib/time';
import { formatVolume, type VolumeUnit } from '@/lib/units';

export interface HistoryCardProps {
  deviceId: string;
  timeZone: string;
}

const TABS: readonly { value: HistoryKind; label: string }[] = [
  { value: 'dispenses', label: 'Dispenses' },
  { value: 'events', label: 'Events' },
  { value: 'syncs', label: 'Check-ins' },
];

type Row = ListRowProps & { key: string };

function rows(kind: HistoryKind, items: History['items'], timeZone: string, unit: VolumeUnit): Row[] {
  if (kind === 'dispenses') {
    return (items as DispenseItem[]).map((item) => ({
      key: `${item.id}`,
      title: formatDateTime(item.received_at, timeZone),
      subtitle: dispenseKind(item.code, item.dose_count),
      value: item.est_volume_ml === null ? '—' : `≈ ${formatVolume(item.est_volume_ml, unit)}`,
    }));
  }
  if (kind === 'events') {
    return (items as EventItem[]).flatMap(describeEventBatch).map((entry) => ({
      key: entry.key,
      title: entry.name,
      subtitle: entry.code ?? undefined,
      value: formatDateTime(entry.at, timeZone),
    }));
  }
  return (items as SyncItem[]).map((item) => ({
    key: `${item.id}`,
    title: formatDateTime(item.started_at, timeZone),
    subtitle: `${item.request_count} ${item.request_count === 1 ? 'request' : 'requests'}`,
    value: item.source_ip,
  }));
}

/** Dispenses, firmware events (named via `lib/events`) and check-ins, newest first, paged. */
export function HistoryCard({ deviceId, timeZone }: HistoryCardProps) {
  const [kind, setKind] = useState<HistoryKind>('dispenses');
  const { unit } = useUnits();
  const history = useDeviceHistory(deviceId, kind);
  const list = (history.data?.pages ?? []).flatMap((page) => rows(kind, page.items, timeZone, unit));
  const idPrefix = `history-${deviceId}`;

  return (
    <SectionCard id="history" title="History" icon="history" collapsible>
      <Tabs label="History" tabs={TABS} selected={kind} onSelect={setKind} idPrefix={idPrefix} />
      <div {...tabPanelProps(idPrefix, kind)} className="flex flex-col gap-3">
        {history.isError && <Notice tone="bad">Couldn’t load the history.</Notice>}
        {history.isPending && <p className="m-0 py-2 text-sm text-dim">Loading…</p>}
        {history.isSuccess && list.length === 0 && <p className="m-0 py-2 text-sm text-dim">Nothing yet.</p>}
        {list.length > 0 && (
          <ul className="m-0 list-none p-0">
            {list.map(({ key, ...row }) => (
              <ListRow key={key} variant="history" {...row} />
            ))}
          </ul>
        )}
        {history.hasNextPage && (
          <Button disabled={history.isFetchingNextPage} onClick={() => void history.fetchNextPage()}>
            Show more
          </Button>
        )}
      </div>
    </SectionCard>
  );
}
