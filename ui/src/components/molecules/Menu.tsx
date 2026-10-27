import { useEffect, useId, useRef, useState, type KeyboardEvent } from 'react';
import { Icon } from '@/components/atoms/Icon';
import { IconButton } from '@/components/atoms/IconButton';
import { cn } from '@/lib/cn';

export interface MenuItem {
  label: string;
  onSelect: () => void;
  /** Danger items (Retire) render in the bad tone. */
  tone?: 'default' | 'danger';
  disabled?: boolean;
}

export interface MenuProps {
  /** Accessible name of the trigger, e.g. "Device actions". */
  label: string;
  items: readonly MenuItem[];
}

/**
 * A "⋯" button opening a short action menu (WAI-ARIA menu button). Arrow keys move, Escape and
 * outside clicks close, and focus returns to the trigger.
 */
export function Menu({ label, items }: MenuProps) {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const listRef = useRef<HTMLUListElement>(null);
  const menuId = useId();

  const enabledItems = () => Array.from(listRef.current?.querySelectorAll<HTMLButtonElement>('[role="menuitem"]:not([disabled])') ?? []);

  useEffect(() => {
    if (!open) return undefined;
    enabledItems()[0]?.focus();
    const onPointerDown = (event: PointerEvent) => {
      const target = event.target as Node;
      if (!listRef.current?.contains(target) && !triggerRef.current?.contains(target)) setOpen(false);
    };
    document.addEventListener('pointerdown', onPointerDown);
    return () => document.removeEventListener('pointerdown', onPointerDown);
  }, [open]);

  const close = () => {
    setOpen(false);
    triggerRef.current?.focus();
  };

  const onKeyDown = (event: KeyboardEvent) => {
    const all = enabledItems();
    const index = all.indexOf(document.activeElement as HTMLButtonElement);
    if (event.key === 'Escape' || event.key === 'Tab') {
      event.preventDefault();
      close();
    } else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      const step = event.key === 'ArrowDown' ? 1 : all.length - 1;
      all[(index + step) % all.length]?.focus();
    }
  };

  return (
    <div className="relative">
      <IconButton
        ref={triggerRef}
        label={label}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        onClick={() => setOpen(!open)}
      >
        <Icon name="more" size={22} strokeWidth={3} />
      </IconButton>
      {open && (
        <ul
          ref={listRef}
          id={menuId}
          role="menu"
          aria-label={label}
          onKeyDown={onKeyDown}
          className="absolute right-0 z-30 m-0 mt-1 flex min-w-56 list-none flex-col rounded-button border border-border bg-surface p-1.5 shadow-card"
        >
          {items.map((item) => (
            <li key={item.label} role="none">
              <button
                type="button"
                role="menuitem"
                disabled={item.disabled}
                onClick={() => {
                  close();
                  item.onSelect();
                }}
                className={cn(
                  'flex min-h-11 w-full cursor-pointer items-center rounded-control px-3 text-left font-medium',
                  'hover:bg-surface2 focus-visible:bg-surface2 disabled:cursor-not-allowed disabled:opacity-50',
                  item.tone === 'danger' ? 'text-bad' : 'text-fg',
                )}
              >
                {item.label}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
