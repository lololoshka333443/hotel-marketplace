import { cva, type VariantProps } from "class-variance-authority";
import { forwardRef, useId, type InputHTMLAttributes } from "react";

import { cn } from "@/utils/cn";

const inputVariants = cva(
  [
    "w-full rounded-lg bg-surface-card text-text-primary",
    // Muted, not the hairline: a control boundary needs 3:1 (WCAG 1.4.11),
    // and the decorative hairline is ~1.2:1. Focus turns the border ink.
    "border border-border-strong transition-colors duration-micro",
    "placeholder:text-text-tertiary",
    "focus:border-border-focus focus:outline-none focus-visible:shadow-focus-ring",
    "aria-[invalid=true]:border-border-error",
    "disabled:bg-surface-disabled disabled:text-text-disabled disabled:cursor-not-allowed",
  ],
  {
    variants: {
      inputSize: {
        sm: "h-size-control-md px-4 text-sm",
        md: "h-size-control-field px-4 text-base",
        lg: "h-size-control-field px-4 text-base",
      },
    },
    defaultVariants: { inputSize: "md" },
  },
);

export interface InputProps
  extends Omit<InputHTMLAttributes<HTMLInputElement>, "size">,
    VariantProps<typeof inputVariants> {
  hasError?: boolean;
  /** A label above the field: 12px, ink-soft, 8px gap (the brief's spec). */
  label?: string;
  /** A 13px message under the field — an error line or a hint. */
  hint?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { inputSize, hasError, label, hint, id, className, ...rest },
  ref,
) {
  const generatedId = useId();
  const fieldId = id ?? generatedId;
  const describedBy = hint ? `${fieldId}-hint` : undefined;

  return (
    <div className="flex flex-col gap-2">
      {label ? (
        <label
          htmlFor={fieldId}
          className="text-xs font-medium tracking-eyebrow uppercase text-text-secondary"
        >
          {label}
        </label>
      ) : null}
      <input
        ref={ref}
        id={fieldId}
        aria-invalid={hasError || undefined}
        aria-describedby={describedBy}
        className={cn(inputVariants({ inputSize }), className)}
        {...rest}
      />
      {hint ? (
        <p
          id={describedBy}
          className={cn(
            "text-[13px] leading-snug",
            hasError ? "text-feedback-error-text" : "text-text-tertiary",
          )}
        >
          {hint}
        </p>
      ) : null}
    </div>
  );
});
