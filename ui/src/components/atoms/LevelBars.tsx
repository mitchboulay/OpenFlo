import { cn } from '@/lib/cn';

export interface LevelBarsProps {
  /** Filled bars, 0–4. */
  level: number;
  /** Fill of the lit bars. Defaults to `bg-fg`. */
  fillClassName?: string;
  className?: string;
}

const HEIGHTS = ['h-[7px]', 'h-[10px]', 'h-[13px]', 'h-4'] as const;

/** Four rising bars (battery cost, Wi-Fi signal). Decorative: always pair it with the level in words. */
export function LevelBars({ level, fillClassName = 'bg-fg', className }: LevelBarsProps) {
  return (
    <span aria-hidden="true" className={cn('flex h-4 flex-none items-end gap-0.5', className)}>
      {HEIGHTS.map((height, index) => (
        <span key={height} className={cn('w-1 rounded-[1px]', height, index < level ? fillClassName : 'bg-border2')} />
      ))}
    </span>
  );
}
