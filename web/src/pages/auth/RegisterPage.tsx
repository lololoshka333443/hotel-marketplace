import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Navigate, Link, useLocation } from "react-router-dom";

import { ApiException, auth, getToken, setToken } from "@/api/client";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { PageShell } from "@/components/PageShell";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";

/**
 * Partner self-registration. On success the app reloads into the cabinet: the
 * token lands in localStorage and the guarded queries re-run authorized.
 */
export function RegisterPage() {
  useDocumentTitle("Регистрация партнёра");
  const location = useLocation();

  // Where to send the partner once the account exists.
  const from = (location.state as { from?: string } | null)?.from ?? "/partner";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);

  const register = useMutation({
    mutationFn: () => auth.register(email, password, name),
    onSuccess: (data) => {
      setToken(data.access_token);
      setError(null);
      // Full navigation so the app boots with the token in place.
      window.location.replace(from);
    },
    onError: (exc) => {
      if (exc instanceof ApiException && exc.status === 409) {
        setError("Партнёр с таким email уже существует. Войдите вместо регистрации.");
      } else {
        setError("Не удалось зарегистрироваться. Попробуйте ещё раз.");
      }
    },
  });

  // Already signed in — no point showing the form.
  if (getToken()) {
    return <Navigate to={from} replace />;
  }

  return (
    <PageShell className="mx-auto max-w-md">
      <h1 className="text-3xl font-bold tracking-tight">Регистрация партнёра</h1>
      <p className="mt-2 text-text-secondary">
        Заведите аккаунт и начните сдавать жильё.
      </p>

      <form
        className="mt-8 space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          register.mutate();
        }}
      >
        <label className="block text-sm">
          <span className="mb-1 block text-text-secondary">Название</span>
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            autoComplete="organization"
            placeholder="Гостевой дом «Маяк»"
            required
            minLength={2}
          />
        </label>
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
            autoComplete="new-password"
            required
            minLength={6}
          />
        </label>
        <p className="text-xs text-text-tertiary">Минимум 6 символов.</p>

        {error ? (
          <p role="alert" className="text-sm text-feedback-error-text">
            {error}
          </p>
        ) : null}

        <Button
          type="submit"
          loading={register.isPending}
          className="w-full"
          size="lg"
        >
          Зарегистрироваться
        </Button>
      </form>

      <p className="mt-6 text-center text-xs text-text-secondary">
        Уже есть аккаунт?{" "}
        <Link to="/login" className="text-text-link hover:text-text-link-hover">
          Войти
        </Link>
      </p>
    </PageShell>
  );
}
