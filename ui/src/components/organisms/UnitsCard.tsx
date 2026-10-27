import { ChoiceChips, type ChoiceChip } from '@/components/molecules/ChoiceChips';
import { SectionCard } from '@/components/molecules/SectionCard';
import { useUnits } from '@/hooks/useUnits';
import type { VolumeUnit } from '@/lib/units';

const OPTIONS: readonly ChoiceChip<VolumeUnit>[] = [
  { value: 'ml', label: 'Milliliters (mL)' },
  { value: 'oz', label: 'Ounces (oz)' },
];

/** Settings → Units: the per-browser volume unit (critique-v2 #5); the default follows the locale. */
export function UnitsCard() {
  const { unit, setUnit } = useUnits();
  return (
    <SectionCard title="Units" icon="drop">
      <ChoiceChips label="Volume unit" options={OPTIONS} selected={unit} onSelect={setUnit} />
      <p className="m-0 text-sm text-dim">Used everywhere in OpenFLO on this device.</p>
    </SectionCard>
  );
}
