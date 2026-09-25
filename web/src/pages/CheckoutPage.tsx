import { useParams } from "react-router-dom";

import { PageShell } from "@/components/PageShell";

export function CheckoutPage() {
  const { bookingId } = useParams();
  return (
    <PageShell>
      <h1 className="text-3xl font-bold tracking-tight">Оплата</h1>
      <p className="mt-2 text-text-secondary">
        Бронь <code className="font-mono text-sm">{bookingId}</code>. Hold,
        таймер 15 минут, выбор оплаты - следующий этап.
      </p>
    </PageShell>
  );
}
