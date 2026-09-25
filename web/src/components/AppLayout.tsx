import { Link, Outlet } from "react-router-dom";

export function AppLayout() {
  return (
    <div className="flex min-h-screen flex-col bg-surface-page text-text-primary font-sans">
      <header className="border-b border-border-default bg-surface-card">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
          <Link to="/" className="flex items-center gap-2 text-lg font-semibold">
            <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-action-primary text-text-on-action">
              ВН
            </span>
            Выше&nbsp;неба
          </Link>
          <nav className="flex items-center gap-1 text-sm sm:gap-2">
            <Link
              to="/search"
              className="rounded-button px-3 py-2 text-text-secondary transition-colors duration-150 hover:bg-interactive-hover hover:text-text-primary"
            >
              Номера
            </Link>
            <Link
              to="/partner"
              className="rounded-button px-3 py-2 text-text-secondary transition-colors duration-150 hover:bg-interactive-hover hover:text-text-primary"
            >
              Партнёру
            </Link>
          </nav>
        </div>
      </header>
      <main className="flex-1">
        <Outlet />
      </main>
      <footer className="border-t border-border-default bg-surface-card py-8 text-sm text-text-secondary">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          Отдых в Коктебеле · мгновенное подтверждение · бесплатная отмена за
          сутки до заезда
        </div>
      </footer>
    </div>
  );
}
