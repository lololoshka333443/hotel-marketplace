import { Link, Outlet, Navigate } from "react-router-dom";

import { getToken, setToken } from "@/api/client";

/**
 * Staff area. One token store serves both partner and admin sessions; the
 * scope is decided by which endpoint issued it (/v1/admin/login here), so the
 * two cabinets never mix.
 */
export function AdminLayout() {
  // The login page lives at /admin/login (outside this layout) to avoid a
  // redirect loop; it sends staff back here on success.
  if (!getToken()) {
    return <Navigate to="/admin/login" state={{ from: "/admin" }} replace />;
  }

  return (
    <div>
      <div className="border-b border-border-default bg-surface-sunken">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-1 px-4 py-3 text-sm sm:px-6 lg:px-8">
          <nav className="flex items-center gap-1">
            <Link
              to="/admin"
              className="rounded-button px-3 py-2 text-text-secondary transition-colors duration-150 hover:bg-interactive-hover hover:text-text-primary"
            >
              Отчёты
            </Link>
            <Link
              to="/admin/moderation"
              className="rounded-button px-3 py-2 text-text-secondary transition-colors duration-150 hover:bg-interactive-hover hover:text-text-primary"
            >
              Модерация
            </Link>
            <Link
              to="/admin/outbox"
              className="rounded-button px-3 py-2 text-text-secondary transition-colors duration-150 hover:bg-interactive-hover hover:text-text-primary"
            >
              События
            </Link>
          </nav>
          <button
            type="button"
            onClick={() => {
              setToken(null);
              window.location.replace("/");
            }}
            className="rounded-button px-3 py-2 text-text-secondary transition-colors duration-150 hover:bg-interactive-hover hover:text-text-primary"
          >
            Выйти
          </button>
        </div>
      </div>
      <Outlet />
    </div>
  );
}
