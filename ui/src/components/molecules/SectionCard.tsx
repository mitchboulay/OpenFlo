import { useId, useState, type ReactNode } from 'react';
import { Icon, type IconName } from '@/components/atoms/Icon';
import { cn } from '@/lib/cn';

export interface SectionCardProps {
  title: string;
  icon: IconName;
  /** Element id, the target of section anchors. */
  id?: string;
  /** Right side of the header, e.g. the battery percent. */
  aside?: ReactNode;
  /** Line under the title. */
  description?: string;
  /** Below `lg`, the body folds behind the header (critique-v2 #7). At `lg`+ it is always open. */
  collapsible?: boolean;
  children: ReactNode;
  className?: string;
}

function TitleRow({ icon, title, aside }: Pick<SectionCardProps, 'icon' | 'title' | 'aside'>) {
  return (
    <>
      <span className="flex size-9 flex-none items-center justify-center rounded-[11px] bg-[image:var(--tileGrad)] text-on-accent">
        <Icon name={icon} size={18} />
      </span>
      <span className="min-w-0 flex-1 text-lg font-[650] tracking-[-0.012em]">{title}</span>
      {aside}
    </>
  );
}

/** A titled card (Dosing, Check-in, Battery…), optionally collapsible on phones. */
export function SectionCard({ title, icon, id, aside, description, collapsible = false, children, className }: SectionCardProps) {
  const [open, setOpen] = useState(false);
  const bodyId = useId();
  const expanded = !collapsible || open;
  return (
    <section
      id={id}
      aria-label={title}
      className={cn('flex scroll-mt-20 flex-col gap-4 rounded-card border border-card-border bg-surface p-5 shadow-card sm:p-[22px]', className)}
    >
      <div className="flex flex-col gap-0.5">
        {collapsible && (
          <h2 className="m-0 lg:hidden">
            <button
              type="button"
              aria-expanded={open}
              aria-controls={bodyId}
              onClick={() => setOpen(!open)}
              className="flex min-h-11 w-full cursor-pointer items-center gap-3 text-left"
            >
              <TitleRow icon={icon} title={title} aside={aside} />
              <Icon name="chevron" size={18} className={cn('text-faint transition-transform', open && 'rotate-90')} />
            </button>
          </h2>
        )}
        <h2 className={cn('m-0 items-center gap-3', collapsible ? 'hidden lg:flex' : 'flex')}>
          <TitleRow icon={icon} title={title} aside={aside} />
        </h2>
        {description && <p className={cn('m-0 text-sm text-dim', !expanded && 'hidden lg:block')}>{description}</p>}
      </div>
      <div id={bodyId} className={cn('flex flex-col gap-4', !expanded && 'hidden lg:flex')}>
        {children}
      </div>
    </section>
  );
}
