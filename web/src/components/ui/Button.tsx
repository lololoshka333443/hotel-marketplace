import { cva, type VariantProps } from "class-variance-authority";
import { Loader2 } from "lucide-react";
import { forwardRef, type ButtonHTMLAttributes } from "react";

import { cn } from "@/utils/cn";

const buttonVariants = cva(
  [
    "inline-flex items-center justify-center gap-2 font-medium",
    "rounded-button transition-colors duration-micro",
    "focus-visible:outline-none focus-visible:shadow-focus-ring",
    // Disabled is a wash fill with muted type — a quiet, paper-y disabled, not
    // a greyed-out SaaS button.
    "disabled:pointer-events-none disabled:bg-surface-disabled disabled:text-text-disabled",
  ],
  {
    variants: {
      variant: {
        primary:
          "bg-action-primary text-text-on-action hover:bg-action-primary-hover active:bg-action-primary-active",
        // Outline: 1px muted border (3:1 — a control boundary), fill washes on hover.
        secondary:
          "bg-transparent text-text-primary border border-border-strong hover:bg-interactive-hover",
        destructive:
          "bg-action-destructive text-text-on-action hover:bg-action-destructive-hover",
        // Text-only: the underline sits 3px off and arrives on hover.
        tertiary:
          "bg-transparent text-text-primary underline-offset-[3px] hover:underline",
        ghost: "bg-transparent text-text-primary hover:bg-interactive-hover",
      },
      size: {
        sm: "h-size-control-sm px-4 text-sm",
        md: "h-size-control-md px-5 text-sm",
        lg: "h-size-control-lg px-6 text-base",
      },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
);

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  loading?: boolean;
  selected?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant, size, loading = false, selected, disabled, className, children, ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      data-variant={variant}
      aria-pressed={selected}
      aria-busy={loading || undefined}
      disabled={disabled || loading}
      className={cn(buttonVariants({ variant, size }), className)}
      {...rest}
    >
      {loading ? (
        <Loader2 className="size-4 animate-spin" aria-hidden="true" />
      ) : null}
      {children}
    </button>
  );
});
