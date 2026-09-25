import { Link, useParams } from "react-router-dom";
import { CheckCircle2 } from "lucide-react";

import { Button } from "@/components/ui/Button";

export function BookingSuccessPage() {
  const { bookingId } = useParams();

  return (
    <div className="mx-auto max-w-2xl px-4 py-16 text-center">
      <div className="mx-auto flex size-16 items-center justify-center rounded-full bg-feedback-success-bg">
        <CheckCircle2
          className="size-8 text-feedback-success-text"
          aria-hidden="true"
        />
      </div>
      <h1 className="mt-6 text-3xl font-bold tracking-tight">
        Бронь подтверждена
      </h1>
      <p className="mt-3 text-text-secondary">
        Мгновенное подтверждение. Мы отправили детали на вашу почту.
      </p>
      {bookingId ? (
        <p className="mt-2 font-mono text-sm text-text-tertiary">{bookingId}</p>
      ) : null}
      <p className="mx-auto mt-6 max-w-md text-sm text-text-secondary">
        Бесплатная отмена до 24:00 дня заезда. После этого срока списывается
        штраф.
      </p>
      <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:justify-center">
        <Link to="/search">
          <Button variant="secondary">Найти ещё жильё</Button>
        </Link>
      </div>
    </div>
  );
}
