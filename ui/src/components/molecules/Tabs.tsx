import { useRef, type KeyboardEvent } from 'react';
import { cn } from '@/lib/cn';

export interface TabsProps<T extends string> {
  /** Accessible name of the tab list, e.g. "History". */
  label: string;
  tabs: readonly { value: T; label: string }[];
  selected: T;
  onSelect: (value: T) => void;
  /** Id prefix linking each tab to its panel (`${idPrefix}-panel`). */
  idPrefix: string;
}

/** Segmented tab list (WAI-ARIA tabs: arrow keys move between tabs). Render the panel with `tabPanelProps`. */
export function Tabs<T extends string>({ label, tabs, selected, onSelect, idPrefix }: TabsProps<T>) {
  const listRef = useRef<HTMLDivElement>(null);

  const onKeyDown = (event: KeyboardEvent) => {
    if (event.key !== 'ArrowRight' && event.key !== 'ArrowLeft') return;
    const index = tabs.findIndex((tab) => tab.value === selected);
    const next = tabs[(index + (event.key === 'ArrowRight' ? 1 : tabs.length - 1)) % tabs.length];
    if (!next) return;
    onSelect(next.value);
    listRef.current?.querySelector<HTMLButtonElement>(`#${idPrefix}-${next.value}`)?.focus();
  };

  return (
    <div ref={listRef} role="tablist" aria-label={label} onKeyDown={onKeyDown} className="flex gap-0.5 rounded-[11px] bg-surface2 p-[3px]">
      {tabs.map((tab) => {
        const active = tab.value === selected;
        return (
          <button
            key={tab.value}
            id={`${idPrefix}-${tab.value}`}
            type="button"
            role="tab"
            aria-selected={active}
            aria-controls={`${idPrefix}-panel`}
            tabIndex={active ? 0 : -1}
            onClick={() => onSelect(tab.value)}
            className={cn(
              'min-h-11 flex-1 cursor-pointer rounded-[9px] text-sm font-semibold',
              active ? 'bg-surface text-fg shadow-raise' : 'text-dim hover:text-fg',
            )}
          >
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}

/** Props for the panel a `Tabs` list controls. */
export function tabPanelProps(idPrefix: string, selected: string) {
  return { id: `${idPrefix}-panel`, role: 'tabpanel', 'aria-labelledby': `${idPrefix}-${selected}` } as const;
}
