import { forwardRef, useState, type InputHTMLAttributes } from 'react';
import { Icon } from '@/components/atoms/Icon';
import { IconButton } from '@/components/atoms/IconButton';
import { Input } from '@/components/atoms/Input';

export type PasswordInputProps = Omit<InputHTMLAttributes<HTMLInputElement>, 'type'>;

/**
 * A password `Input` with a show/hide toggle. Pass `autoComplete` (`new-password` or
 * `current-password`). Field's `id`/`aria-*` props land on the input.
 */
export const PasswordInput = forwardRef<HTMLInputElement, PasswordInputProps>(function PasswordInput(props, ref) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="relative">
      <Input
        ref={ref}
        type={visible ? 'text' : 'password'}
        autoCapitalize="off"
        autoCorrect="off"
        spellCheck={false}
        {...props}
        className="pr-13"
      />
      <IconButton
        label={visible ? 'Hide password' : 'Show password'}
        aria-pressed={visible}
        onClick={() => setVisible(!visible)}
        className="absolute top-1/2 right-1 -translate-y-1/2"
      >
        <Icon name={visible ? 'eyeOff' : 'eye'} size={20} />
      </IconButton>
    </div>
  );
});
