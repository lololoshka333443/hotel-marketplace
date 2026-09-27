import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy, KeyRound, Plus, Trash2 } from "lucide-react";

import { partner } from "@/api/client";
import type { ApiKeyOut, ApiKeyWithSecret } from "@/api/types";import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";

/**
 * Channel write-API keys. A channel pushes bookings with the key instead of a
 * JWT; the key is scoped to this partner's inventory only.
 *
 * The plaintext exists in exactly one place: the create response. It is never
 * stored or re-shown, so the partner must copy it right away.
 */
export function ApiKeys() {
  const { data: keys, isPending } = useQuery({
    queryKey: ["api-keys"],
    queryFn: ({ signal }) => partner.apiKeys.list(signal),
  });
  const [created, setCreated] = useState<ApiKeyWithSecret | null>(null);

  return (
    <section className="mt-10">
      <h2 className="text-xl font-semibold">API-ключи каналов</h2>
      <p className="mt-2 max-w-2xl text-sm text-text-secondary">
        Канал (площадка или менеджер каналов) толкает бронирования через
        API-ключ. Ключ видит только ваши объекты и не может обойти закрытые
        даты или перебронировать занятое.
      </p>

      {isPending ? (
        <p role="status" className="mt-4 text-sm text-text-secondary">
          Загружаем ключи…
        </p>
      ) : keys && keys.length > 0 ? (
        <ul className="mt-4 space-y-3">
          {keys.map((key) => (
            <ApiKeyRow key={key.id} apiKey={key} />
          ))}
        </ul>
      ) : (
        <p className="mt-4 rounded-lg border border-border-default bg-surface-card p-4 text-sm text-text-secondary">
          Ключей пока нет. Создайте один, чтобы подключить канал.
        </p>
      )}

      <div className="mt-4">
        <CreateKeyButton onCreated={setCreated} />
      </div>

      <Modal
        open={created !== null}
        onClose={() => setCreated(null)}
        titleId="api-key-created-title"
        title="Ключ создан"
      >
        <p className="mt-2 text-sm text-text-secondary">
          Скопируйте ключ сейчас — показать его снова невозможно. Если ключ
          утечёт, отзовите его и создайте новый.
        </p>
        <div className="mt-4">
          <Input
            readOnly
            value={created?.key ?? ""}
            aria-label="Новый API-ключ"
            className="font-mono"
          />
        </div>
        <div className="mt-6 flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={() => setCreated(null)}>
            Готово
          </Button>
          <Button
            type="button"
            onClick={() => {
              if (created) void copy(created.key);
            }}
          >
            <Copy className="size-4" aria-hidden="true" />
            Копировать
          </Button>
        </div>
      </Modal>
    </section>
  );
}

function ApiKeyRow({ apiKey }: { apiKey: ApiKeyOut }) {
  const queryClient = useQueryClient();
  const [confirmOpen, setConfirmOpen] = useState(false);

  const remove = useMutation({
    mutationFn: () => partner.apiKeys.remove(apiKey.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["api-keys"] });
      setConfirmOpen(false);
    },
  });

  const used = apiKey.last_used_at
    ? new Date(apiKey.last_used_at).toLocaleString("ru-RU")
    : "не использовался";

  return (
    <li className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 rounded-lg border border-border-default bg-surface-card p-4">
      <div className="flex items-center gap-3">
        <KeyRound className="size-5 shrink-0 text-text-tertiary" aria-hidden="true" />
        <div>
          <p className="font-medium">{apiKey.label}</p>
          <p className="font-mono text-xs text-text-tertiary">{apiKey.key_prefix}…</p>
          <p className="text-xs text-text-tertiary">Использован: {used}</p>
        </div>
      </div>
      <Button variant="ghost" size="sm" onClick={() => setConfirmOpen(true)}>
        <Trash2 className="size-4" aria-hidden="true" />
        Отозвать
      </Button>

      <Modal
        open={confirmOpen}
        onClose={() => setConfirmOpen(false)}
        titleId={`api-key-revoke-${apiKey.id}`}
        title="Отозвать ключ?"
      >
        <p className="mt-2 text-text-secondary">
          Канал больше не сможет бронировать этим ключом. Брони, которые он уже
          создал, остаются.
        </p>
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
            loading={remove.isPending}
            onClick={() => remove.mutate()}
          >
            Отозвать ключ
          </Button>
        </div>
      </Modal>
    </li>
  );
}

function CreateKeyButton({
  onCreated,
}: {
  onCreated: (key: ApiKeyWithSecret) => void;
}) {
  const [open, setOpen] = useState(false);
  const [label, setLabel] = useState("");

  const create = useMutation({
    mutationFn: () => partner.apiKeys.create(label.trim()),
    onSuccess: (key) => {
      setLabel("");
      setOpen(false);
      onCreated(key);
    },
  });

  return (
    <>
      <Button variant="secondary" onClick={() => setOpen(true)}>
        <Plus className="size-4" aria-hidden="true" />
        Создать ключ
      </Button>
      <Modal
        open={open}
        onClose={() => setOpen(false)}
        titleId="api-key-create-title"
        title="Новый API-ключ"
      >
        <p className="mt-2 text-sm text-text-secondary">
          Назовите ключ так, чтобы было понятно, какой канал им пользуется.
        </p>
        <form
          className="mt-6 space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            if (label.trim()) create.mutate();
          }}
        >
          <label className="block text-sm">
            <span className="mb-1 block text-text-secondary">Название</span>
            <Input
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="Например: Суточно.ру"
              required
              minLength={2}
            />
          </label>
          {create.isError ? (
            <p role="alert" className="text-sm text-feedback-error-text">
              Не удалось создать ключ. Попробуйте ещё раз.
            </p>
          ) : null}
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="secondary" onClick={() => setOpen(false)}>
              Отмена
            </Button>
            <Button
              type="submit"
              loading={create.isPending}
              disabled={label.trim().length < 2}
            >
              Создать
            </Button>
          </div>
        </form>
      </Modal>
    </>
  );
}

async function copy(text: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    // clipboard may be unavailable (insecure context); the input is readonly
    // and focused so the user can select+copy manually
  }
}
