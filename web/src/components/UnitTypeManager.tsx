import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";

import { partner } from "@/api/client";
import { humanError } from "@/utils/errors";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";

/**
 * Unit types of one property: the rows of the chessboard and the thing guests
 * actually book. A partner with no unit types has an empty calendar and an
 * unbookable listing, so creating them is the step right after the property.
 */
export function UnitTypeManager({ propertyId }: { propertyId: string }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);

  const { data: unitTypes } = useQuery({
    queryKey: ["unit-types", propertyId],
    queryFn: ({ signal }) => partner.listUnitTypes(propertyId, signal),
  });

  const list = unitTypes ?? [];

  function refresh() {
    void queryClient.invalidateQueries({ queryKey: ["unit-types", propertyId] });
    // The chessboard renders one row per unit type, so it follows along.
    void queryClient.invalidateQueries({ queryKey: ["calendar", propertyId] });
  }

  return (
    <section className="mt-10">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 className="font-serif text-2xl font-normal">Номера</h2>
          <p className="mt-2 max-w-2xl text-sm text-text-secondary">
            Типы номеров этого объекта — это то, что бронируют гости. Каждый
            становится строкой в шахматке.
          </p>
        </div>
        <Button
          variant="secondary"
          onClick={() => setOpen(true)}
          className="shrink-0"
        >
          <Plus className="size-4" aria-hidden="true" />
          Добавить номер
        </Button>
      </div>

      {list.length === 0 ? (
        <p className="mt-4 rounded-xl border border-border-default bg-surface-card p-6 text-sm text-text-secondary">
          У объекта ещё нет номеров. Добавьте первый — и в шахматке появится
          расписание по датам.
        </p>
      ) : (
        <ul className="mt-4 divide-y divide-border-default border-y border-border-default">
          {list.map((unit) => (
            <li
              key={unit.id}
              className="flex items-center justify-between py-4"
            >
              <div>
                <p className="font-medium">{unit.name}</p>
                <p className="mt-1 text-sm text-text-secondary">
                  до {unit.capacity} человек · {unit.total_units}{" "}
                  {plural(unit.total_units, "номер", "номера", "номеров")}
                </p>
              </div>
            </li>
          ))}
        </ul>
      )}

      <CreateUnitTypeModal
        propertyId={propertyId}
        open={open}
        onClose={() => setOpen(false)}
        onCreated={refresh}
      />
    </section>
  );
}

function CreateUnitTypeModal({
  propertyId,
  open,
  onClose,
  onCreated,
}: {
  propertyId: string;
  open: boolean;
  onClose: () => void;
  onCreated: () => void;
}) {
  const [name, setName] = useState("");
  const [capacity, setCapacity] = useState(2);
  const [totalUnits, setTotalUnits] = useState(1);

  const create = useMutation({
    mutationFn: () =>
      partner.createUnitType({
        property_id: propertyId,
        name,
        capacity,
        total_units: totalUnits,
      }),
    onSuccess: () => {
      setName("");
      setCapacity(2);
      setTotalUnits(1);
      onCreated();
      onClose();
    },
  });

  return (
    <Modal
      open={open}
      onClose={onClose}
      titleId="create-unit-type-title"
      title="Новый номер"
    >
      <p className="mt-2 text-sm text-text-secondary">
        Инвентарь создаётся сразу — календарь не будет пустым.
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
          placeholder="Например: Стандарт с видом на море"
          required
          minLength={2}
        />
        <div className="grid grid-cols-2 gap-3">
          <Input
            label="Вместимость"
            type="number"
            min={1}
            max={20}
            value={capacity}
            onChange={(e) => setCapacity(Number(e.target.value) || 1)}
            required
          />
          <Input
            label="Всего номеров"
            type="number"
            min={1}
            max={100}
            value={totalUnits}
            onChange={(e) => setTotalUnits(Number(e.target.value) || 1)}
            required
          />
        </div>
        {create.isError ? (
          <p role="alert" className="text-sm text-feedback-error-text">
            {humanError(
              create.error,
              "Не удалось создать номер. Попробуйте ещё раз.",
            )}
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
            Создать номер
          </Button>
        </div>
      </form>
    </Modal>
  );
}

function plural(n: number, one: string, few: string, many: string): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return one;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return few;
  return many;
}
