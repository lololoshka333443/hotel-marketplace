import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Navigate, useLocation } from "react-router-dom";

import { auth, getToken, setToken } from "@/api/client";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { PageShell } from "@/components/PageShell";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";

/**
 * Partner login. On success the app reloads into the return-to location: the
 * token lands in localStorage and the guarded queries re-run authorized.
 */
export function LoginPage() {
  useDocumentTitle("Вход для партнёра");
  const location = useLocation();

  // Where to send the partner after a successful login.
  const from = (location.state as { from?: string } | null)?.from ?? "/partner";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  const login = useMutation({
    mutationFn: () => auth.login(email, password),
    onSuccess: (data) => {
      setToken(data.access_token);
      setError(null);
      // Full navigation so the app boots with the token in place.
      window.location.replace(from);
    },
    onError: () => setError("Неверный email или пароль. Попробуйте ещё раз."),
  });

  // Already signed in - no point showing the form.
  if (getToken()) {
    return <Navigate to={from} replace />;
  }

  return (
    <PageShell className="mx-auto max-w-md">
      <h1 className="text-3xl font-bold tracking-tight">Вход для партнёра</h1>
      <p className="mt-2 text-text-secondary">
        Управляйте объектами, ценами и бронированиями.
      </p>

      <form
        className="mt-8 space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          login.mutate();
        }}
      >
        <label className="block text-sm">
          <span className="mb-1 block text-text-secondary">Email</span>
          <Input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
            placeholder="name@example.com"
            required
          />
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-text-secondary">Пароль</span>
          <Input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
        </label>

        {error ? (
          <p role="alert" className="text-sm text-feedback-error-text">
            {error}
          </p>
        ) : null}

        <Button
          type="submit"
          loading={login.isPending}
          className="w-full"
          size="lg"
        >
          Войти
        </Button>
      </form>

      <p className="mt-6 text-center text-xs text-text-secondary">
        Демо-доступ: demo@example.com / demo-password
      </p>
    </PageShell>
  );
}
