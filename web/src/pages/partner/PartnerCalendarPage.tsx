import { PageShell } from "@/components/PageShell";

export function PartnerCalendarPage() {
  return (
    <PageShell className="max-w-none">
      <h1 className="text-3xl font-bold tracking-tight">Шахматка</h1>
      <p className="mt-2 text-text-secondary">
        Доступность по датам: ряды - типы номеров, колонки - даты. Следующий
        этап.
      </p>
    </PageShell>
  );
}
