import { useEffect, useId, useRef, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { Icon } from '@/components/atoms/Icon';
import { IconButton } from '@/components/atoms/IconButton';
import { useFocusTrap } from '@/hooks/useFocusTrap';

export interface SheetProps {
  open: boolean;
  /** Called on Escape, overlay tap or the close button. */
  onClose: () => void;
  /** Visible heading; also the dialog's accessible name. */
  title: string;
  children: ReactNode;
  /** Actions pinned under the content, e.g. Cancel + Save. */
  footer?: ReactNode;
}

/**
 * Modal surface: a bottom sheet below `sm`, a centered dialog at `sm`+.
 * Traps focus, closes on Escape and restores focus on close.
 */
export function Sheet({ open, onClose, title, children, footer }: SheetProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const titleId = useId();
  useFocusTrap(panelRef, open, onClose);

  useEffect(() => {
    if (!open) return undefined;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [open]);

  if (!open) return null;

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-end justify-center sm:items-center sm:p-6">
      <div aria-hidden="true" className="absolute inset-0 bg-overlay" onClick={onClose} />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        className="relative flex max-h-[90dvh] w-full flex-col rounded-t-sheet border border-card-border bg-surface shadow-card sm:max-w-md sm:rounded-sheet"
      >
        <div className="flex items-center gap-2 px-5 pt-4 pb-2">
          <h2 id={titleId} className="m-0 flex-1 text-lg font-semibold">
            {title}
          </h2>
          <IconButton label="Close" onClick={onClose}>
            <Icon name="close" size={18} />
          </IconButton>
        </div>
        <div className="overflow-y-auto px-5 pb-5">{children}</div>
        {footer && (
          <div className="flex flex-wrap justify-end gap-3 border-t border-border px-5 py-4 pb-[max(1rem,env(safe-area-inset-bottom))]">
            {footer}
          </div>
        )}
      </div>
    </div>,
    document.body,
  );
}
