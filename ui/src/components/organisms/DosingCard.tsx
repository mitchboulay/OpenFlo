import { useState } from 'react';
import { Button } from '@/components/atoms/Button';
import { Icon } from '@/components/atoms/Icon';
import { SectionCard } from '@/components/molecules/SectionCard';
import type { DeviceDetail } from '@/api/types';
import { AdvancedDosingSheet } from './AdvancedDosingSheet';
import { BottleLevel } from './BottleLevel';
import { DoseControl } from './DoseControl';
import { LiquidPicker } from './LiquidPicker';

export interface DosingCardProps {
  device: DeviceDetail;
}

/** Dosing = Liquid · Dose · Bottle (critique-v2 #1). Everything else lives under Advanced or in the header. */
export function DosingCard({ device }: DosingCardProps) {
  const [advancedOpen, setAdvancedOpen] = useState(false);
  return (
    <SectionCard id="dosing" title="Dosing" icon="drop" className="gap-5">
      <LiquidPicker device={device} />
      <DoseControl device={device} />
      <BottleLevel device={device} />
      <div className="-mx-5 -mb-5 border-t border-border sm:-mx-[22px] sm:-mb-[22px]">
        <Button
          variant="ghost"
          aria-haspopup="dialog"
          className="w-full justify-between rounded-none rounded-b-card px-5 py-4 text-fg sm:px-[22px]"
          onClick={() => setAdvancedOpen(true)}
        >
          Advanced
          <Icon name="chevron" size={18} className="text-faint" />
        </Button>
      </div>
      <AdvancedDosingSheet open={advancedOpen} device={device} onClose={() => setAdvancedOpen(false)} />
    </SectionCard>
  );
}
