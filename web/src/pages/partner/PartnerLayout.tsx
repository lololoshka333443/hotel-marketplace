import { Outlet } from "react-router-dom";

export function PartnerLayout() {
  return (
    <div className="border-b border-border-default bg-surface-sunken">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <nav className="flex h-14 items-center gap-1 text-sm">
          <a
            href="/partner"
            className="rounded-radius-button px-3 py-2 text-text-secondary hover:bg-interactive-hover hover:text-text-primary"
          >
            Объекты
          </a>
          <a
            href="/partner/calendar"
            className="rounded-radius-button px-3 py-2 text-text-secondary hover:bg-interactive-hover hover:text-text-primary"
          >
            Шахматка
          </a>
        </nav>
      </div>
      <Outlet />
    </div>
  );
}
