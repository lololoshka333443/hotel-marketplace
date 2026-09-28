import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Navigate, useLocation, useNavigate } from "react-router-dom";

import { admin, getToken, setToken } from "@/api/client";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { PageShell } from "@/components/PageShell";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";

/** Staff login. Separate endpoint from the partner cabinet (scope: admin). */
export function AdminLoginPage() {
  useDocumentTitle("Вход для администратора");
  const location = useLocation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const from =
    (location.state as { from?: string } | null)?.from ?? "/admin";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  const login = useMutation({
    mutationFn: () => admin.login(email, password),
    onSuccess: (data) => {
      setToken(data.access_token);
      setError(null);
      // Anonymous cache must not survive the token.
      queryClient.clear();
      navigate(from, { replace: true });
    },
    onError: () =>
      setError("Неверный email или пароль. Попробуйте ещё раз."),
  });

  if (getToken()) {
    return <Navigate to={from} replace />;
  }

  return (
    <PageShell className="mx-auto max-w-md">
      <h1 className="text-3xl font-bold tracking-tight">Вход для администратора</h1>
      <p className="mt-2 text-text-secondary">
        Отчёты по комиссии и модерация объектов.
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
        Демо-доступ: admin@example.com / admin-password
      </p>
    </PageShell>
  );
}
