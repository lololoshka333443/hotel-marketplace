import { PageShell } from "@/components/PageShell";

export function HomePage() {
  return (
    <PageShell className="mx-auto max-w-4xl">
      <section className="rounded-radius-lg bg-gradient-to-b from-surface-sunken to-surface-card p-8 sm:p-12">
        <h1 className="text-4xl font-bold leading-tight tracking-tight sm:text-5xl">
          Жильё в Крыму — мгновенное подтверждение
        </h1>
        <p className="mt-4 text-lg text-text-secondary">
          Отели, квартиры и апартаменты у моря. 100% предоплата, бесплатная
          отмена за сутки до заезда.
        </p>
        <a
          href="/search"
          className="mt-8 inline-flex h-12 items-center justify-center rounded-radius-button bg-action-primary px-6 text-base font-semibold text-text-on-action transition-colors duration-150 hover:bg-action-primary-hover"
        >
          Найти жильё
        </a>
      </section>
    </PageShell>
  );
}
