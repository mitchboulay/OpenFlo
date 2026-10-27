/** Display unit for liquid volumes. The API always speaks mL; this is presentation only. */
export type VolumeUnit = 'ml' | 'oz';

export const ML_PER_OZ = 29.5735;

export const UNIT_LABEL: Record<VolumeUnit, string> = { ml: 'mL', oz: 'oz' };

/** Stepper increment in the display unit. */
export const VOLUME_STEP: Record<VolumeUnit, number> = { ml: 5, oz: 0.5 };

/** mL → a number in `unit`, rounded for display (whole mL; oz to 0.1 below 10, else whole). */
export function toDisplay(ml: number, unit: VolumeUnit): number {
  if (unit === 'ml') return Math.round(ml);
  const oz = ml / ML_PER_OZ;
  return oz < 10 ? Math.round(oz * 10) / 10 : Math.round(oz);
}

/** A number typed or stepped in `unit` → mL (unrounded; the API validates). */
export function fromDisplay(value: number, unit: VolumeUnit): number {
  return unit === 'ml' ? value : value * ML_PER_OZ;
}

/** The single volume formatter: "177 mL" or "6.0 oz". */
export function formatVolume(ml: number, unit: VolumeUnit): string {
  const value = toDisplay(ml, unit);
  const text = unit === 'oz' && value < 10 ? value.toFixed(1) : String(value);
  return `${text} ${UNIT_LABEL[unit]}`;
}

/** A flow rate: "27.2 mL/s" or "0.92 oz/s". */
export function formatFlow(mlPerSecond: number, unit: VolumeUnit): string {
  const value = unit === 'ml' ? mlPerSecond.toFixed(1) : (mlPerSecond / ML_PER_OZ).toFixed(2);
  return `${value} ${UNIT_LABEL[unit]}/s`;
}

/** "28–816 mL" */
export function formatVolumeRange(minMl: number, maxMl: number, unit: VolumeUnit): string {
  const low = formatVolume(minMl, unit).split(' ')[0];
  return `${low}–${formatVolume(maxMl, unit)}`;
}

/** The other unit, for the "≈ 6.0 oz" subline. */
export function otherUnit(unit: VolumeUnit): VolumeUnit {
  return unit === 'ml' ? 'oz' : 'ml';
}

/** Locale default: US English uses fluid ounces, everyone else millilitres. */
export function defaultUnitForLocale(locale: string | undefined): VolumeUnit {
  return locale?.toLowerCase() === 'en-us' ? 'oz' : 'ml';
}
