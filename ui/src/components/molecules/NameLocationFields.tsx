import { Input } from '@/components/atoms/Input';
import { ChoiceChips } from './ChoiceChips';
import { Field } from './Field';

/** The API's limits on a device's labels (`DeviceUpdate`, `ClaimRequest`, `ProvisioningCreate`). */
export const MAX_DEVICE_NAME = 40;
export const MAX_DEVICE_LOCATION = 60;

export interface NameLocationFieldsProps {
  name: string;
  location: string;
  onNameChange: (name: string) => void;
  onLocationChange: (location: string) => void;
  /** An API error, shown under the name. */
  error?: string | null;
  /** Tap-to-fill locations shown under the location field. */
  suggestions?: readonly string[];
}

/** A device's name and location: the edit sheet, the claim sheet and the add-device wizard. */
export function NameLocationFields({
  name,
  location,
  onNameChange,
  onLocationChange,
  error,
  suggestions,
}: NameLocationFieldsProps) {
  return (
    <div className="flex flex-col gap-4">
      <Field label="Name" error={error}>
        <Input
          value={name}
          onChange={(event) => onNameChange(event.target.value)}
          maxLength={MAX_DEVICE_NAME}
          placeholder="Attic unit"
          autoComplete="off"
          required
        />
      </Field>
      <Field label="Where is it?" hint="So you can find it later.">
        <Input
          value={location}
          onChange={(event) => onLocationChange(event.target.value)}
          maxLength={MAX_DEVICE_LOCATION}
          placeholder="Air handler, attic"
          autoComplete="off"
        />
      </Field>
      {suggestions && suggestions.length > 0 && (
        <ChoiceChips
          label="Suggested locations"
          options={suggestions.map((suggestion) => ({ value: suggestion, label: suggestion }))}
          selected={suggestions.includes(location) ? location : null}
          onSelect={onLocationChange}
        />
      )}
    </div>
  );
}
