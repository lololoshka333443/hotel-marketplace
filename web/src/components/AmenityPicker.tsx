import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check, Sparkles } from "lucide-react";

import { partner } from "@/api/client";
import { AMENITY_CATALOG, amenityLabel, type PropertyOut } from "@/api/types";
import { humanError } from "@/utils/errors";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { cn } from "@/utils/cn";

/**
 * Amenity picker: what the property offers, shown to the guest as icons.
 *
 * The keys come from the backend catalog, so the cabinet and the catalog can
 * never show two labels for the same thing. Saving sends the whole selection
 * (the PATCH is a full replace, not an append) and the mutation holds the
 * optimistic list until the server answers, so a slow save does not freeze
 * the toggles.
 */
export function AmenityPicker({
  property,
}: {
  property: PropertyOut;
}) {
  const [open, setOpen] = useState(false);
  const selected = property.amenities ?? [];

  return (
    <>
      <Button
        variant="secondary"
        onClick={() => setOpen(true)}
        aria-label="Редактировать удобства"
      >
        <Sparkles className="size-4" aria-hidden="true" />
        Удобства
        {selected.length > 0 ? (
          <span className="ml-1 text-text-tertiary">{selected.length}</span>
        ) : null}
      </Button>
      <Modal
        open={open}
        onClose={() => setOpen(false)}
        titleId={`amenities-${property.id}`}
        title={`Удобства — ${property.name}`}
      >
        <AmenityForm property={property} onClose={() => setOpen(false)} />
      </Modal>
    </>
  );
}

function AmenityForm({
  property,
  onClose,
}: {
  property: PropertyOut;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [picked, setPicked] = useState<string[]>(property.amenities ?? []);

  const save = useMutation({
    mutationFn: () => partner.updateProperty(property.id, { amenities: picked }),
    onSuccess: () => {
      // The guest's page shows these; it must not read a stale list.
      void queryClient.invalidateQueries({ queryKey: ["properties"] });
      void queryClient.invalidateQueries({ queryKey: ["property"] });
      void queryClient.invalidateQueries({ queryKey: ["partner-properties"] });
      onClose();
    },
  });

  const toggle = (key: string) => {
    setPicked((current) =>
      current.includes(key)
        ? current.filter((k) => k !== key)
        : [...current, key],
    );
  };

  return (
    <div className="mt-2">
      <p className="text-sm text-text-secondary">
        Отмечено {picked.length} из {AMENITY_CATALOG.length}. Гость видит
        удобства на странице объекта.
      </p>

      <ul className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-2">
        {AMENITY_CATALOG.map(({ key }) => {
          const on = picked.includes(key);
          return (
            <li key={key}>
              <button
                type="button"
                aria-pressed={on}
                onClick={() => toggle(key)}
                className={cn(
                  "flex h-size-control-md w-full items-center gap-3 rounded-lg border px-4 text-left text-sm transition-colors duration-micro focus:outline-none focus-visible:shadow-focus-ring",
                  on
                    ? "border-border-strong bg-interactive-active text-text-primary"
                    : "border-border-strong bg-surface-card text-text-secondary hover:bg-interactive-hover",
                )}
              >
                <span
                  className={cn(
                    "flex size-5 shrink-0 items-center justify-center rounded-full border",
                    on
                      ? "border-border-strong bg-surface-card text-text-primary"
                      : "border-border-strong text-transparent",
                  )}
                >
                  <Check className="size-3" aria-hidden="true" />
                </span>
                {amenityLabel(key)}
              </button>
            </li>
          );
        })}
      </ul>

      {save.isError ? (
        <p role="alert" className="mt-4 text-sm text-feedback-error-text">
          {humanError(save.error, "Не удалось сохранить удобства. Попробуйте ещё раз.")}
        </p>
      ) : null}

      <div className="mt-6 flex justify-end gap-2">
        <Button type="button" variant="secondary" onClick={onClose}>
          Отмена
        </Button>
        <Button
          type="button"
          loading={save.isPending}
          disabled={
            picked.length === (property.amenities ?? []).length &&
            picked.every((k) => (property.amenities ?? []).includes(k))
          }
          onClick={() => save.mutate()}
        >
          Сохранить
        </Button>
      </div>
    </div>
  );
}
