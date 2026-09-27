import { cva, type VariantProps } from "class-variance-authority";
import { forwardRef, type InputHTMLAttributes } from "react";

import { cn } from "@/utils/cn";

const inputVariants = cva(
  [
    "w-full rounded-button bg-surface-card text-text-primary",
    // border-strong, not default: the control outline needs 3:1 (WCAG 1.4.11).
    "border border-border-strong transition-colors duration-150",
    "placeholder:text-text-tertiary",
    "hover:border-border-focus",
    "focus:border-border-focus focus:outline-none focus-visible:shadow-focus-ring",
    "aria-[invalid=true]:border-border-error",
    "disabled:bg-surface-disabled disabled:text-text-disabled disabled:cursor-not-allowed",
  ],
  {
    variants: {
      inputSize: {
        sm: "h-size-control-sm px-3 text-sm",
        md: "h-size-control-md px-4 text-sm",
        lg: "h-size-control-lg px-4 text-base",
      },
    },
    defaultVariants: { inputSize: "md" },
  },
);

export interface InputProps
  extends Omit<InputHTMLAttributes<HTMLInputElement>, "size">,
    VariantProps<typeof inputVariants> {
  hasError?: boolean;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { inputSize, hasError, className, ...rest },
  ref,
) {
  return (
    <input
      ref={ref}
      aria-invalid={hasError || undefined}
      className={cn(inputVariants({ inputSize }), className)}
      {...rest}
    />
  );
});
