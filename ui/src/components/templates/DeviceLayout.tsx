import type { ReactNode } from 'react';
import { SectionNav } from '@/components/molecules/SectionNav';

export interface DeviceLayoutProps {
  /** Status header and any warnings, full width. */
  header: ReactNode;
  /** Anchors under the header, e.g. Dosing · Schedule · Device. `device` targets the secondary column. */
  sections: readonly { id: string; label: string }[];
  /** The device's job: Dosing, Schedule. Left column at `lg`. */
  primary: ReactNode;
  /** The device itself: Check-in, Battery, Info, History. Right column at `lg`. */
  secondary: ReactNode;
}

/** Device page structure: one column below `lg`, two at `lg`+. */
export function DeviceLayout({ header, sections, primary, secondary }: DeviceLayoutProps) {
  return (
    <div className="flex flex-col gap-4">
      {header}
      <SectionNav label="Device sections" sections={sections} />
      <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
        <div className="flex min-w-0 flex-col gap-4">{primary}</div>
        <div id="device" aria-label="Device" role="region" className="flex min-w-0 scroll-mt-20 flex-col gap-4">
          {secondary}
        </div>
      </div>
    </div>
  );
}
