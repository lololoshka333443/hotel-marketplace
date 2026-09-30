import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { admin } from "@/api/client";
import type { AdminProperty, AdminPropertyStatus } from "@/api/types";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";

const FILTERS: { value: string; label: string }[] = [
  { value: "", label: "Все" },
  { value: "pending_moderation", label: "На модерации" },
  { value: "published", label: "Опубликованы" },
  { value: "draft", label: "Черновики" },
  { value: "blocked", label: "Заблокированы" },
];

/** Moderation queue: every property with admin status actions. */
export function AdminModerationPage() {
  useDocumentTitle("Модерация - админка");
  const [filter, setFilter] = useState("");
  const queryClient = useQueryClient();

  const { data, isPending, isError } = useQuery({
    queryKey: ["admin-properties", filter],
    queryFn: ({ signal }) => admin.properties(filter || null, signal),
  });

  const mutate = useMutation({
    mutationFn: ({ id, status }: { id: string; status: AdminPropertyStatus }) =>
      admin.setStatus(id, status),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["admin-properties"] }),
  });

  const list = data ?? [];

  return (
    <div className="mx-auto max-w-[1120px] px-4 py-16 sm:px-6 lg:px-8">
      <p className="text-xs font-medium uppercase tracking-eyebrow text-text-secondary">
        Админка
      </p>
      <h1 className="mt-4 font-serif text-4xl font-normal leading-display tracking-tight">
        Модерация объектов
      </h1>
      <p className="mt-4 text-text-secondary">
        Партнёры могут публиковать объекты сами; админ следит и блокирует
        нарушения.
      </p>

      <div className="mt-6 flex flex-wrap gap-2">
        {FILTERS.map((f) => (
          <Button
            key={f.value}
            variant={filter === f.value ? "primary" : "secondary"}
            size="sm"
            selected={filter === f.value}
            onClick={() => setFilter(f.value)}
          >
            {f.label}
          </Button>
        ))}
      </div>

      {isPending ? (
        <p role="status" className="mt-10 text-text-secondary">
          Загружаем объекты…
        </p>
      ) : isError ? (
        <div className="mt-10 flex flex-wrap items-center gap-4">
          <p role="alert" className="text-feedback-error-text">
            Не удалось загрузить объекты. Обновите страницу.
          </p>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => queryClient.invalidateQueries({ queryKey: ["admin-properties"] })}
          >
            Попробовать снова
          </Button>
        </div>
      ) : list.length === 0 ? (
        <p className="mt-10 rounded-xl border border-border-default bg-surface-card p-6 text-text-secondary">
          В этом разделе нет объектов. Выберите другой фильтр.
        </p>
      ) : (
        <ul className="mt-6 space-y-3">
          {list.map((property) => (
            <li
              key={property.id}
              className="flex flex-col gap-3 rounded-xl border border-border-default bg-surface-card p-4 sm:flex-row sm:items-center sm:justify-between"
            >
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="text-lg font-medium">{property.name}</h2>
                  <StatusBadge status={property.status} />
                </div>
                <p className="mt-1 text-sm text-text-secondary">
                  {property.city || "без города"} · {property.partner_email}
                </p>
              </div>
              <div className="flex shrink-0 flex-wrap gap-2">
                <Actions
                  property={property}
                  disabled={mutate.isPending}
                  onAct={(status) =>
                    mutate.mutate({ id: property.id, status })
                  }
                />
              </div>
            </li>
          ))}
        </ul>
      )}

      {mutate.isError ? (
        <p role="alert" className="mt-4 text-sm text-feedback-error-text">
          Не удалось изменить статус объекта. Попробуйте ещё раз.
        </p>
      ) : null}
    </div>
  );
}

/** Only transitions the backend allows (illegal ones answer 409). */
function Actions({
  property,
  disabled,
  onAct,
}: {
  property: AdminProperty;
  disabled: boolean;
  onAct: (status: AdminPropertyStatus) => void;
}) {
  switch (property.status) {
    case "pending_moderation":
      return (
        <>
          <Button size="sm" disabled={disabled} onClick={() => onAct("published")}>
            Опубликовать
          </Button>
          <Button
            size="sm"
            variant="secondary"
            disabled={disabled}
            onClick={() => onAct("draft")}
          >
            Вернуть в черновики
          </Button>
        </>
      );
    case "published":
      return (
        <Button
          size="sm"
          variant="destructive"
          disabled={disabled}
          onClick={() => onAct("blocked")}
        >
          Заблокировать
        </Button>
      );
    case "blocked":
      return (
        <Button size="sm" disabled={disabled} onClick={() => onAct("published")}>
          Восстановить
        </Button>
      );
    case "draft":
      return (
        <Button size="sm" disabled={disabled} onClick={() => onAct("published")}>
          Опубликовать
        </Button>
      );
  }
}

function StatusBadge({ status }: { status: AdminPropertyStatus }) {
  switch (status) {
    case "published":
      return <Badge variant="success">Опубликован</Badge>;
    case "pending_moderation":
      return <Badge variant="warning">На модерации</Badge>;
    case "blocked":
      return <Badge variant="error">Заблокирован</Badge>;
    default:
      return <Badge variant="neutral">Черновик</Badge>;
  }
}
