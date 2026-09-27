import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy, RefreshCw } from "lucide-react";

import { partner } from "@/api/client";
import type { UnitTypeOut } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";

/**
 * iCal export per unit type. The feed is pull-based: the channel polls the
 * secret URL and reads blocked dates (bookings, holds, stop sell) as BUSY.
 */
export function IcalExport({ propertyId }: { propertyId: string }) {
  const { data: unitTypes } = useQuery({
    queryKey: ["unit-types", propertyId],
    queryFn: () => partner.listUnitTypes(propertyId),
  });

  if (!unitTypes || unitTypes.length === 0) {
    return null;
  }

  return (
    <section className="mt-10">
      <h2 className="text-xl font-semibold">iCal-экспорт</h2>
      <p className="mt-2 max-w-2xl text-sm text-text-secondary">
        Внешний канал читает заблокированные даты по этой ссылке: брони, холды
        и закрытые даты видны как занятые. Свободные даты остаются доступными.
      </p>
      <ul className="mt-4 space-y-3">
        {unitTypes.map((unitType) => (
          <IcalRow key={unitType.id} unitType={unitType} />
        ))}
      </ul>
    </section>
  );
}

function IcalRow({ unitType }: { unitType: UnitTypeOut }) {
  const queryClient = useQueryClient();
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [copied, setCopied] = useState(false);

  const { data: feed, isPending, isError } = useQuery({
    queryKey: ["ical-feed", unitType.id],
    queryFn: ({ signal }) => partner.icalFeed.get(unitType.id, signal),
  });

  const rotate = useMutation({
    mutationFn: () => partner.icalFeed.rotate(unitType.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ical-feed", unitType.id] });
      setConfirmOpen(false);
    },
  });

  async function copy(url: string) {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard blocked (insecure context): the URL is selectable in the
      // input below, so the guest can still copy it manually.
    }
  }

  return (
    <li className="flex flex-col gap-3 rounded-lg border border-border-default bg-surface-card p-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0">
        <p className="font-medium">{unitType.name}</p>
        {feed ? (
          <input
            readOnly
            value={feed.url}
            aria-label={`Ссылка iCal для ${unitType.name}`}
            className="mt-1 w-full truncate rounded-button border border-border-strong bg-surface-card px-3 py-1.5 font-mono text-xs text-text-secondary focus:border-border-focus focus:outline-none"
          />
        ) : isPending ? (
          <p role="status" className="mt-1 text-xs text-text-secondary">
            Загружаем ссылку…
          </p>
        ) : isError ? (
          <p className="mt-1 text-xs text-text-secondary">
            Ссылка ещё не создана.
          </p>
        ) : null}
      </div>

      <div className="flex shrink-0 gap-2">
        {feed ? (
          <>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => copy(feed.url)}
            >
              <Copy className="size-4" aria-hidden="true" />
              {copied ? "Скопировано" : "Копировать"}
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setConfirmOpen(true)}
            >
              <RefreshCw className="size-4" aria-hidden="true" />
              Обновить ссылку
            </Button>
          </>
        ) : (
          <Button
            size="sm"
            onClick={() => rotate.mutate()}
            loading={rotate.isPending}
          >
            Создать ссылку
          </Button>
        )}
      </div>

      <Modal
        open={confirmOpen}
        onClose={() => setConfirmOpen(false)}
        titleId={`ical-rotate-${unitType.id}`}
        title="Обновить ссылку?"
      >
        <p className="mt-2 text-text-secondary">
          Текущая ссылка перестанет работать сразу. Каналам понадобится новая.
        </p>
        {rotate.isError ? (
          <p role="alert" className="mt-3 text-sm text-feedback-error-text">
            Не удалось обновить ссылку. Попробуйте ещё раз.
          </p>
        ) : null}
        <div className="mt-6 flex justify-end gap-2">
          <Button
            type="button"
            variant="secondary"
            onClick={() => setConfirmOpen(false)}
          >
            Отмена
          </Button>
          <Button
            type="button"
            variant="destructive"
            loading={rotate.isPending}
            onClick={() => rotate.mutate()}
          >
            Обновить ссылку
          </Button>
        </div>
      </Modal>
    </li>
  );
}
