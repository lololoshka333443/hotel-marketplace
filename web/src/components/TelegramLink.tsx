import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy, RefreshCw, Send, Unlink } from "lucide-react";

import { partner } from "@/api/client";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { humanError } from "@/utils/errors";

/**
 * The partner's Telegram channel.
 *
 * Linking is a one-time code the partner copies into the bot: the cabinet never
 * knows the chat id, and the bot never knows the partner's password. The code
 * rotates on every use and on every unlink, so a leaked screenshot of this
 * section cannot bind a stranger's chat to someone's notifications.
 */
export function TelegramLink() {
  const queryClient = useQueryClient();
  const { data, isPending } = useQuery({
    queryKey: ["telegram"],
    queryFn: ({ signal }) => partner.telegram.status(signal),
  });

  const rotate = useMutation({
    mutationFn: () => partner.telegram.rotate(),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["telegram"] });
    },
  });

  const unlink = useMutation({
    mutationFn: () => partner.telegram.unlink(),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["telegram"] });
    },
  });

  function copyCode() {
    if (!data) return;
    void navigator.clipboard.writeText(data.link_code).catch(() => {
      // clipboard may be unavailable (insecure context); the input stays
      // focused and selected so the partner can copy manually
    });
  }

  return (
    <section className="mt-10">
      <h2 className="font-serif text-2xl font-normal">Telegram</h2>
      <p className="mt-2 max-w-2xl text-sm text-text-secondary">
        Уведомления о подтверждённых бронях приходят в бот: код, гость, даты и
        сумма с комиссией.
      </p>

      {isPending || !data ? (
        <p role="status" className="mt-4 text-sm text-text-secondary">
          Загружаем настройки…
        </p>
      ) : (
        <div className="mt-4 space-y-4">
          {data.chat_id ? (
            <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 rounded-xl border border-border-default bg-surface-card p-4">
              <div>
                <p className="text-sm text-text-primary">
                  Привязан чат{" "}
                  <span className="font-mono">{data.chat_id}</span>
                </p>
                <p className="mt-1 text-sm text-text-tertiary">
                  Уведомления о новых бронях приходят сюда.
                </p>
              </div>
              <div className="flex gap-2">
                <Button
                  type="button"
                  variant="secondary"
                  loading={rotate.isPending}
                  onClick={() => rotate.mutate()}
                >
                  <RefreshCw className="size-4" aria-hidden="true" />
                  Новый код
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  loading={unlink.isPending}
                  onClick={() => unlink.mutate()}
                >
                  <Unlink className="size-4" aria-hidden="true" />
                  Отключить
                </Button>
              </div>
            </div>
          ) : null}

          <div className="rounded-xl border border-border-default bg-surface-card p-4">
            <Input
              label="Код привязки"
              value={data.link_code}
              readOnly
              hint={
                data.chat_id
                  ? "Код обновлён. Отправьте его в бот, чтобы привязать другой чат."
                  : "Отправьте боту команду /start и этот код."
              }
              className="font-mono"
            />
            <div className="mt-4 flex flex-wrap gap-2">
              <Button type="button" onClick={copyCode}>
                <Copy className="size-4" aria-hidden="true" />
                Скопировать код
              </Button>
              <Button
                type="button"
                variant="secondary"
                loading={rotate.isPending}
                onClick={() => rotate.mutate()}
              >
                <RefreshCw className="size-4" aria-hidden="true" />
                Обновить код
              </Button>
            </div>
            {rotate.isError ? (
              <p role="alert" className="mt-4 text-sm text-feedback-error-text">
                {humanError(rotate.error, "Не удалось обновить код. Попробуйте ещё раз.")}
              </p>
            ) : null}
            {unlink.isError ? (
              <p role="alert" className="mt-4 text-sm text-feedback-error-text">
                {humanError(unlink.error, "Не удалось отключить чат. Попробуйте ещё раз.")}
              </p>
            ) : null}
          </div>

          <p className="flex items-center gap-2 text-sm text-text-tertiary">
            <Send className="size-4 shrink-0" aria-hidden="true" />
            Найдите бота и отправьте{" "}
            <code className="rounded bg-surface-disabled px-1.5 py-0.5 font-mono text-xs">
              /start ВАШ_КОД
            </code>
            . Код одноразовый и обновляется после привязки.
          </p>
        </div>
      )}
    </section>
  );
}
