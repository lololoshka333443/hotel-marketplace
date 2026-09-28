import { Link, Outlet, useNavigate } from "react-router-dom";
import { Moon, Sun } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";

import { getToken, setToken } from "@/api/client";
import { useTheme } from "@/hooks/useTheme";

export function AppLayout() {
  const { theme, toggle } = useTheme();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  return (
    <div className="flex min-h-screen flex-col bg-surface-page text-text-primary font-sans">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-modal focus:rounded-button focus:bg-action-primary focus:px-4 focus:py-2 focus:text-text-on-action focus:shadow-overlay"
      >
        К основному содержимому
      </a>
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
            <button
              type="button"
              onClick={toggle}
              aria-label={
                theme === "dark" ? "Включить светлую тему" : "Включить тёмную тему"
              }
              className="inline-flex size-9 items-center justify-center rounded-button text-text-secondary transition-colors duration-150 hover:bg-interactive-hover hover:text-text-primary focus-visible:shadow-focus-ring"
            >
              {theme === "dark" ? (
                <Sun className="size-5" aria-hidden="true" />
              ) : (
                <Moon className="size-5" aria-hidden="true" />
              )}
            </button>
            {getToken() ? (
              <>
                <Link
                  to="/partner"
                  className="rounded-button px-3 py-2 text-text-secondary transition-colors duration-150 hover:bg-interactive-hover hover:text-text-primary"
                >
                  Кабинет
                </Link>
                <button
                  type="button"
                  onClick={() => {
                    setToken(null);
                    // Anonymous cache must not survive the token.
                    queryClient.clear();
                    navigate("/", { replace: true });
                  }}
                  className="rounded-button px-3 py-2 text-text-secondary transition-colors duration-150 hover:bg-interactive-hover hover:text-text-primary"
                >
                  Выйти
                </button>
              </>
            ) : (
              <Link
                to="/login"
                className="rounded-button px-3 py-2 text-text-secondary transition-colors duration-150 hover:bg-interactive-hover hover:text-text-primary"
              >
                Партнёру
              </Link>
            )}
          </nav>
        </div>
      </header>
      <main id="main" tabIndex={-1} className="flex-1 focus:outline-none">
        <Outlet />
      </main>
      <footer className="border-t border-border-default bg-surface-card py-8 text-sm text-text-secondary">
        <div className="mx-auto flex max-w-7xl flex-col gap-2 px-4 sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-8">
          <p>
            Отдых в Коктебеле · мгновенное подтверждение · бесплатная отмена за
            сутки до заезда
          </p>
          <Link to="/admin" className="text-text-link hover:text-text-link-hover">
            Админка
          </Link>
        </div>
      </footer>
    </div>
  );
}
