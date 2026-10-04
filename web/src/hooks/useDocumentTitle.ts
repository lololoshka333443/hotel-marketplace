import { useEffect } from "react";

/**
 * Per-page document titles (WCAG 2.4.2). React Router v7 renders one index.html,
 * so without this every screen shares the bundle title.
 */
const BASE = "Выше неба";

export function useDocumentTitle(title?: string) {
  useEffect(() => {
    document.title = title ? `${title} - ${BASE}` : BASE;
    return () => {
      document.title = BASE;
    };
  }, [title]);
}
