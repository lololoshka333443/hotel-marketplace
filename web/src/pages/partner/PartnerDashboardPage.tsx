import { useQuery, useMutation } from "@tanstack/react-query";
import { Link, Navigate } from "react-router-dom";
import { BedDouble, Building2, Plus } from "lucide-react";
import { useState } from "react";

import { partner, getToken } from "@/api/client";
import { humanError } from "@/utils/errors";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Modal } from "@/components/ui/Modal";
import { Input } from "@/components/ui/Input";
import { PropertyPhotos } from "@/components/PropertyPhotos";
import { AmenityPicker } from "@/components/AmenityPicker";
import type { PropertyOut } from "@/api/types";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { plural } from "@/utils/plural";

const PROPERTY_TYPES: { value: PropertyOut["property_type"]; label: string }[] = [
  { value: "hotel", label: "Отель" },
  { value: "apartment", label: "Квартира" },
  { value: "house", label: "Дом" },
  { value: "room", label: "Комната" },
  { value: "hostel", label: "Хостел" },
];

export function PartnerDashboardPage() {
  useDocumentTitle("Мои объекты - кабинет партнёра");
  const { data: properties, isPending, isError } = useQuery({
    queryKey: ["partner-properties"],
    queryFn: () => partner.listProperties(),
    enabled: Boolean(getToken()),
  });

  const [createOpen, setCreateOpen] = useState(false);
  const openCreate = () => setCreateOpen(true);

  // The login form lives on /login; it sends the partner back here on success.
  if (!getToken()) {
    return <Navigate to="/login" state={{ from: "/partner" }} replace />;
  }
  if (isPending) {
    return (
      <div className="mx-auto max-w-[1120px] px-4 py-16 text-text-secondary sm:px-6 lg:px-8">
        <p role="status">Загружаем объекты…</p>
      </div>
    );
  }
  if (isError) {
    return (
      <div className="mx-auto max-w-[1120px] px-4 py-16 sm:px-6 lg:px-8">
        <h1 className="font-serif text-4xl font-normal leading-display tracking-tight">
          Не удалось загрузить объекты
        </h1>
        <p className="mt-2 text-text-secondary">
          Обновите страницу. Если ошибка остаётся, мы уже о ней знаем.
        </p>
        <Button
          variant="secondary"
          className="mt-6"
          onClick={() => window.location.reload()}
        >
          Обновить страницу
        </Button>
      </div>
    );
  }

  const list = (properties ?? []) as PropertyOut[];

  return (
    <div className="mx-auto max-w-[1120px] px-4 py-16 sm:px-6 lg:px-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs font-medium uppercase tracking-eyebrow text-text-secondary">
            Кабинет партнёра
          </p>
          <h1 className="mt-4 font-serif text-4xl font-normal leading-display tracking-tight">
            Мои объекты
          </h1>
          <p className="mt-2 text-text-secondary">
            {list.length === 0
              ? "Здесь появятся ваши отели, квартиры и апартаменты"
              : `${list.length} ${plural(list.length, "объект", "объекта", "объектов")}`}
          </p>
        </div>
        <Button onClick={openCreate}>
          <Plus className="size-4" aria-hidden="true" />
          Добавить объект
        </Button>
      </div>

      {list.length === 0 ? <EmptyState onAdd={openCreate} /> : <PropertyList properties={list} />}

      <CreateModal open={createOpen} onClose={() => setCreateOpen(false)} />
    </div>
  );
}

/** First-run state: explain the value, one dominant action. No "No data". */
function EmptyState({ onAdd }: { onAdd: () => void }) {
  return (
    <div className="mt-8 rounded-xl border border-border-default bg-surface-card p-8 sm:p-12">
      <div className="mx-auto flex size-14 items-center justify-center rounded-button bg-surface-sunken">
        <Building2 className="size-7 text-text-secondary" aria-hidden="true" />
      </div>
      <h2 className="mt-6 text-center font-serif text-2xl font-normal">
        Заведите первый объект
      </h2>
      <p className="mx-auto mt-3 max-w-md text-center text-text-secondary">
        Гости бронируют и оплачивают у нас, вы получаете подтверждённые
        бронирования. Настройте цены и доступность, дальше всё работает
        автоматически.
      </p>
      <div className="mt-8 flex justify-center">
        <Button size="lg" onClick={onAdd}>
          <Plus className="size-4" aria-hidden="true" />
          Добавить объект
        </Button>
      </div>
      <ol className="mx-auto mt-10 grid max-w-lg gap-4 text-sm sm:grid-cols-3">
        <Step n="1" title="Опишите жильё">
          Тип, город, условия заезда
        </Step>
        <Step n="2" title="Задайте цены">
          Базовый тариф и сезонные надбавки
        </Step>
        <Step n="3" title="Принимайте брони">
          Мгновенное подтверждение и оплата
        </Step>
      </ol>
    </div>
  );
}

function Step({ n, title, children }: { n: string; title: string; children: React.ReactNode }) {
  return (
    <li className="rounded-xl bg-surface-sunken p-4">
      <p className="font-mono text-xs text-text-tertiary">Шаг {n}</p>
      <p className="mt-1 font-medium">{title}</p>
      <p className="mt-1 text-text-secondary">{children}</p>
    </li>
  );
}

function PropertyList({ properties }: { properties: PropertyOut[] }) {
  return (
    <ul className="mt-8 space-y-4">
      {properties.map((property) => {
        const type = PROPERTY_TYPES.find((t) => t.value === property.property_type);
        return (
          <li
            key={property.id}
            className="flex flex-col gap-4 rounded-xl border border-border-default bg-surface-card p-5 sm:flex-row sm:items-center sm:justify-between"
          >
            <div className="flex items-start gap-4">
              <div className="flex size-11 shrink-0 items-center justify-center rounded-button bg-surface-sunken">
                <BedDouble className="size-5 text-text-secondary" aria-hidden="true" />
              </div>
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="text-lg font-medium">{property.name}</h2>
                  <StatusBadge status={property.status} />
                </div>
                <p className="mt-1 text-sm text-text-secondary">
                  {type?.label ?? property.property_type} · {property.city || "Крым"}
                </p>
                <p className="mt-1 text-xs text-text-tertiary">
                  Заезд {fmtTime(property.checkin_time)} · выезд{" "}
                  {fmtTime(property.checkout_time)}
                </p>
              </div>
            </div>
            <div className="flex shrink-0 flex-wrap gap-2">
              <PropertyPhotos
                propertyId={property.id}
                propertyName={property.name}
              />
              <AmenityPicker property={property} />
              <Link to="/partner/calendar">
                <Button variant="secondary">Шахматка</Button>
              </Link>
            </div>
          </li>
        );
      })}
    </ul>
  );
}

function StatusBadge({ status }: { status: PropertyOut["status"] }) {
  switch (status) {
    case "published":
      return <Badge variant="success">Опубликован</Badge>;
    case "pending_moderation":
      return <Badge variant="warning">На модерации</Badge>;
    case "blocked":
      return <Badge variant="error">Заблокирован</Badge>;
    default:
      return <Badge variant="neutral">Черновик</Badge>;
  }
}

function fmtTime(t: string): string {
  // Backend sends "14:00:00" (datetime.time); show "14:00".
  return t.slice(0, 5);
}

function CreateModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [name, setName] = useState("");
  const [propertyType, setPropertyType] =
    useState<PropertyOut["property_type"]>("apartment");
  const [city, setCity] = useState("");

  const create = useMutation({
    mutationFn: () =>
      partner.createProperty({ name, property_type: propertyType, city }),
    onSuccess: () => {
      setName("");
      setCity("");
      onClose();
      window.location.reload();
    },
  });

  return (
    <Modal
      open={open}
      onClose={onClose}
      titleId="create-property-title"
      title="Новый объект"
    >
      <p className="mt-2 text-sm text-text-secondary">
        Поля можно изменить позже. После наполнения объект публикуется.
      </p>
      <form
        className="mt-6 space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          create.mutate();
        }}
      >
        <Input
          label="Название"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Например: Отель у моря"
          required
          minLength={2}
        />
        <div className="flex flex-col gap-2">
          <span className="text-xs font-medium uppercase tracking-eyebrow text-text-secondary">
            Тип жилья
          </span>
          <select
            value={propertyType}
            onChange={(e) =>
              setPropertyType(e.target.value as PropertyOut["property_type"])
            }
            className="h-size-control-field w-full rounded-lg border border-border-strong bg-surface-card px-4 text-base text-text-primary focus:border-border-focus focus:outline-none focus-visible:shadow-focus-ring"
          >
            {PROPERTY_TYPES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </div>
        <Input
          label="Город"
          value={city}
          onChange={(e) => setCity(e.target.value)}
          placeholder="Например: Коктебель"
        />
        {create.isError ? (
          <p role="alert" className="text-sm text-feedback-error-text">
            {humanError(create.error, "Не удалось создать объект. Попробуйте ещё раз.")}
          </p>
        ) : null}
        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="secondary" onClick={onClose}>
            Отмена
          </Button>
          <Button
            type="submit"
            loading={create.isPending}
            disabled={name.length < 2}
          >
            Создать объект
          </Button>
        </div>
      </form>
    </Modal>
  );
}
