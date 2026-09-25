import { useParams } from "react-router-dom";

import { PageShell } from "@/components/PageShell";

export function PropertyPage() {
  const { id } = useParams();
  return (
    <PageShell>
      <h1 className="text-3xl font-bold tracking-tight">Карточка объекта</h1>
      <p className="mt-2 text-text-secondary">
        Объект <code className="font-mono text-sm">{id}</code>. Фото, тарифы,
        панель бронирования — следующий этап.
      </p>
    </PageShell>
  );
}
