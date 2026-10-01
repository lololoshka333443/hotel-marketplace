import { Link } from "react-router-dom";

import { Button } from "@/components/ui/Button";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";

/**
 * The SPA fallback serves index.html on any path, so an unknown URL still runs
 * the app — it needs a real screen, not a blank page with a working header.
 */
export function NotFoundPage() {
  useDocumentTitle("Страница не найдена");

  return (
    <div className="mx-auto max-w-2xl px-4 py-32 text-center">
      <p className="text-xs font-medium uppercase tracking-eyebrow text-text-secondary">
        Ошибка 404
      </p>
      <h1 className="mt-6 font-serif text-display font-normal leading-display tracking-tight">
        Такой страницы нет
      </h1>
      <p className="mt-6 text-lg leading-normal text-text-secondary">
        Возможно, ссылка устарела или была введена с опечаткой.
      </p>
      <div className="mt-10 flex flex-col gap-3 sm:flex-row sm:justify-center">
        <Link to="/">
          <Button variant="secondary">На главную</Button>
        </Link>
        <Link to="/search">
          <Button variant="tertiary">Найти жильё</Button>
        </Link>
      </div>
    </div>
  );
}
