import { Link, Outlet } from "react-router-dom";

export function PartnerLayout() {
  return (
    <div>
      <div className="border-b border-border-default bg-surface-sunken">
        <div className="mx-auto flex max-w-7xl items-center gap-1 px-4 py-3 text-sm sm:px-6 lg:px-8">
          <Link
            to="/partner"
            className="rounded-button px-3 py-2 text-text-secondary transition-colors duration-150 hover:bg-interactive-hover hover:text-text-primary"
          >
            Объекты
          </Link>
          <Link
            to="/partner/calendar"
            className="rounded-button px-3 py-2 text-text-secondary transition-colors duration-150 hover:bg-interactive-hover hover:text-text-primary"
          >
            Шахматка
          </Link>
        </div>
      </div>
      <Outlet />
    </div>
  );
}
