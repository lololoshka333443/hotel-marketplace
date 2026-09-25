import { Outlet } from "react-router-dom";

import { cn } from "@/utils/cn";

export function AppLayout() {
  return (
    <div className="min-h-screen bg-surface-page text-text-primary font-sans">
      <header className="border-b border-border-default bg-surface-card">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
          <a href="/" className="flex items-center gap-2 text-lg font-semibold">
            <span
              className={cn(
                "inline-flex h-8 w-8 items-center justify-center rounded-lg",
                "bg-action-primary text-text-on-action",
              )}
            >
              КР
            </span>
            Крым&nbsp;Сей
          </a>
          <nav className="flex items-center gap-1 text-sm sm:gap-2">
            <a
              href="/search"
              className="rounded-button px-3 py-2 text-text-secondary hover:bg-interactive-hover hover:text-text-primary"
            >
              Поиск
            </a>
            <a
              href="/partner"
              className="rounded-button px-3 py-2 text-text-secondary hover:bg-interactive-hover hover:text-text-primary"
            >
              Кабинет партнёра
            </a>
          </nav>
        </div>
      </header>
      <main>
        <Outlet />
      </main>
      <footer className="border-t border-border-default bg-surface-card py-8 text-sm text-text-secondary">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          Бронирование жилья в Крыму · мгновенное подтверждение · бесплатная
          отмена за сутки до заезда
        </div>
      </footer>
    </div>
  );
}
