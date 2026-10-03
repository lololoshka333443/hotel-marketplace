import { useCallback, useEffect, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";

import type { Photo } from "@/api/types";
import { Modal } from "@/components/ui/Modal";

/**
 * The lightbox for a property's photos.
 *
 * Reuses the shared Modal (focus trap, Escape, return focus) and adds the
 * arrow keys a lightbox is expected to answer. Modal closes on the scrim
 * click; arrows stay inside the dialog because the key handler is local.
 */
export function PhotoLightbox({
  photos,
  index,
  onClose,
  title,
}: {
  photos: Photo[];
  index: number;
  onClose: () => void;
  title: string;
}) {
  const [current, setCurrent] = useState(index);

  const step = useCallback(
    (delta: number) => {
      if (photos.length <= 1) return;
      // Wrapping is deliberate: a ring, not a dead end at either edge.
      setCurrent((i) => (i + delta + photos.length) % photos.length);
    },
    [photos.length],
  );

  useEffect(() => {
    if (photos.length <= 1) return;
    function onKey(event: KeyboardEvent) {
      if (event.key === "ArrowLeft") {
        event.preventDefault();
        step(-1);
      } else if (event.key === "ArrowRight") {
        event.preventDefault();
        step(1);
      }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [step, photos.length]);

  const photo = photos[current];

  return (
    <Modal
      open
      onClose={onClose}
      titleId="photo-lightbox-title"
      className="max-w-4xl p-0"
      title={
        <span className="sr-only">
          {title} — фото {current + 1} из {photos.length}
        </span>
      }
    >
      <div className="relative">
        <img
          src={photo.full}
          alt={`${title} — фото ${current + 1} из ${photos.length}`}
          className="max-h-[80vh] w-full rounded-xl object-contain"
        />

        {photos.length > 1 ? (
          <>
            <button
              type="button"
              onClick={() => step(-1)}
              className="absolute left-2 top-1/2 grid size-11 -translate-y-1/2 place-items-center rounded-full bg-scrim text-white transition-opacity duration-micro hover:opacity-80 focus:outline-none focus-visible:shadow-focus-ring"
              aria-label="Предыдущее фото"
            >
              <ChevronLeft className="size-5" aria-hidden="true" />
            </button>
            <button
              type="button"
              onClick={() => step(1)}
              className="absolute right-2 top-1/2 grid size-11 -translate-y-1/2 place-items-center rounded-full bg-scrim text-white transition-opacity duration-micro hover:opacity-80 focus:outline-none focus-visible:shadow-focus-ring"
              aria-label="Следующее фото"
            >
              <ChevronRight className="size-5" aria-hidden="true" />
            </button>
            <p className="absolute bottom-2 left-1/2 -translate-x-1/2 rounded-full bg-scrim px-3 py-1 text-xs text-white">
              {current + 1} / {photos.length}
            </p>
          </>
        ) : null}
      </div>
    </Modal>
  );
}
