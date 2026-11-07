import { useId } from 'react';

interface ConsentCheckboxProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
}

const linkClass =
  'font-medium text-primary underline underline-offset-2 hover:text-primary/80 focus:outline-none focus:ring-2 focus:ring-primary rounded-sm';

/**
 * Age and policy consent, shared by the sign-up form and the OAuth finish step.
 * Unticked by default (the parent owns the state). The two links open in a new
 * tab so a half-filled form survives the read.
 */
export default function ConsentCheckbox({
  checked,
  onChange,
  disabled = false,
}: ConsentCheckboxProps) {
  const id = useId();
  return (
    <div className="flex min-h-11 items-start gap-3">
      <input
        aria-labelledby={`${id}-text`}
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(event) => onChange(event.target.checked)}
        className="mt-0.5 h-5 w-5 shrink-0 accent-primary focus:ring-2 focus:ring-primary focus:outline-none"
      />
      {/* Named by aria-labelledby and toggled by the span's own click, rather than a
          <label for>: a click on a link inside a label activates the box in some
          engines. The links stay clickable; only text outside them toggles. */}
      <span
        id={`${id}-text`}
        onClick={(event) => {
          if (disabled || (event.target as Element).closest('a')) return;
          onChange(!checked);
        }}
        className="text-sm text-ink-2 cursor-pointer"
      >
        I am 13 or older, and I have read and accept the{' '}
        <a href="/privacy" target="_blank" rel="noopener" className={linkClass}>
          Privacy Policy
        </a>{' '}
        and{' '}
        <a href="/terms" target="_blank" rel="noopener" className={linkClass}>
          Terms of Service
        </a>
        .
      </span>
    </div>
  );
}
