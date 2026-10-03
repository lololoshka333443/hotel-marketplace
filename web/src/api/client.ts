/**
 * Thin typed fetch client for the API.
 *
 * All routes are under /v1 (proxied to FastAPI in dev, same origin in prod).
 * The token is read from localStorage; the auth endpoints don't need it.
 */

import type {
  ApiKeyOut,
  ApiKeyWithSecret,
  ApiError,
  AuthMe,
  AvailabilityResponse,
  BookingOut,
  CalendarResponse,
  CommissionReport,
  IcalFeed,
  IcalSubscription,
  OutboxEvent,
  OutboxMetrics,
  RatePlan,
  ReconciliationReport,
  SyncResult,
  WebhookOut,
  AdminProperty,
  AdminPropertyStatus,
  HoldConflict,
  PartnerBookingOut,
  HoldRequest,
  PropertyOut,
  PropertyPublic,
  PropertyPage,
  PropertyType,
  Photo,
  TokenResponse,
  UnitTypeOut,
} from "./types";

const BASE = "/v1";
const TOKEN_KEY = "hm_access_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null): void {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
  } else {
    localStorage.removeItem(TOKEN_KEY);
  }
}

export class ApiException extends Error {
  status: number;
  reason?: string;

  constructor(status: number, detail: string, reason?: string) {
    super(detail);
    this.name = "ApiException";
    this.status = status;
    this.reason = reason;
  }
}

function toIsoDate(value: string): string {
  // Normalizes "YYYY-MM-DD" (accepts full datetimes too, strips the time).
  return value.slice(0, 10);
}

async function request<T>(
  path: string,
  options: {
    method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
    body?: unknown;
    signal?: AbortSignal;
    headers?: Record<string, string>;
  } = {},
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    Accept: "application/json",
    ...options.headers,
  };
  if (token) headers.Authorization = `Bearer ${token}`;
  // FormData takes its own boundary in Content-Type — never stringify it.
  const isFormData =
    typeof FormData !== "undefined" && options.body instanceof FormData;
  if (options.body !== undefined && !isFormData) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(`${BASE}${path}`, {
    method: options.method ?? "GET",
    headers,
    body:
      options.body === undefined
        ? undefined
        : isFormData
          ? (options.body as FormData)
          : JSON.stringify(options.body),
    signal: options.signal,
  });

  const text = await response.text();
  const data = text ? JSON.parse(text) : null;

  if (!response.ok) {
    const err = (data ?? {}) as Partial<ApiError> & Partial<HoldConflict>;
    throw new ApiException(
      response.status,
      err.detail ?? `request failed: ${response.status}`,
      err.reason,
    );
  }

  return data as T;
}

// ---- auth -----------------------------------------------------------------

export const auth = {
  register: (email: string, password: string, name: string) =>
    request<TokenResponse>("/auth/register", {
      method: "POST",
      body: { email, password, name },
    }),
  login: (email: string, password: string) =>
    request<TokenResponse>("/auth/login", {
      method: "POST",
      body: { email, password },
    }),
  me: () => request<AuthMe>("/auth/me"),
};

// ---- public catalog -------------------------------------------------------

export const catalog = {
  list: (
    city?: string,
    guests?: number,
    q?: string,
    dateFrom?: string,
    dateTo?: string,
    limit = 24,
    offset = 0,
    signal?: AbortSignal,
  ) => {
    const params = new URLSearchParams();
    if (city) params.set("city", city);
    if (guests) params.set("guests", String(guests));
    if (q) params.set("q", q);
    if (dateFrom) params.set("date_from", dateFrom);
    if (dateTo) params.set("date_to", dateTo);
    params.set("limit", String(limit));
    params.set("offset", String(offset));
    return request<PropertyPage>(`/properties?${params.toString()}`, {
      signal,
    });
  },
  get: (id: string, signal?: AbortSignal) =>
    request<PropertyPublic>(`/properties/${id}`, { signal }),
  listUnitTypes: (propertyId: string, signal?: AbortSignal) =>
    request<UnitTypeOut[]>(
      `/public/unit-types/${encodeURIComponent(propertyId)}`,
      { signal },
    ),
};

export const availability = {
  get: (
    unitTypeId: string,
    dateFrom: string,
    dateTo: string,
    signal?: AbortSignal,
  ) =>
    request<AvailabilityResponse>(
      `/availability?unit_type_id=${encodeURIComponent(
        unitTypeId,
      )}&date_from=${toIsoDate(dateFrom)}&date_to=${toIsoDate(dateTo)}`,
      { signal },
    ),
};

// ---- booking (guest flow) -------------------------------------------------

export const bookings = {
  hold: (payload: HoldRequest, idempotencyKey?: string) =>
    request<BookingOut>("/bookings/hold", {
      method: "POST",
      body: payload,
      headers: idempotencyKey
        ? { "Idempotency-Key": idempotencyKey }
        : undefined,
    }),
  get: (id: string, signal?: AbortSignal) =>
    request<BookingOut>(`/bookings/${id}`, { signal }),
  byCode: (code: string, signal?: AbortSignal) =>
    request<BookingOut>(`/bookings/by-code/${encodeURIComponent(code)}`, {
      signal,
    }),
  pay: (id: string) =>
    request<BookingOut>(`/bookings/${id}/pay`, { method: "POST" }),
  cancel: (id: string) =>
    request<BookingOut>(`/bookings/${id}/cancel`, { method: "POST" }),
  refund: (id: string) =>
    request<BookingOut>(`/bookings/${id}/refund`, { method: "POST" }),
};

// ---- admin ----------------------------------------------------------------

export const admin = {
  login: (email: string, password: string) =>
    request<TokenResponse>("/admin/login", {
      method: "POST",
      body: { email, password },
    }),
  report: (from: string | null, to: string | null, signal?: AbortSignal) => {
    const qs = new URLSearchParams();
    if (from) qs.set("date_from", from);
    if (to) qs.set("date_to", to);
    const tail = qs.toString();
    return request<CommissionReport>(
      `/admin/reports/commission${tail ? `?${tail}` : ""}`,
      { signal },
    );
  },
  properties: (status: string | null, signal?: AbortSignal) => {
    const qs = status ? `?status=${encodeURIComponent(status)}` : "";
    return request<AdminProperty[]>(`/admin/properties${qs}`, { signal });
  },
  setStatus: (propertyId: string, status: AdminPropertyStatus) =>
    request<AdminProperty>(`/admin/properties/${propertyId}/status`, {
      method: "PATCH",
      body: { status },
    }),
  outbox: (status: string | null, signal?: AbortSignal) => {
    const qs = status ? `?status=${encodeURIComponent(status)}` : "";
    return request<OutboxEvent[]>(`/admin/outbox${qs}`, { signal });
  },
  outboxMetrics: (signal?: AbortSignal) =>
    request<OutboxMetrics>("/admin/outbox/metrics", { signal }),
  reconciliation: (
    dateFrom: string | null,
    dateTo: string | null,
    signal?: AbortSignal,
  ) => {
    const qs = [
      dateFrom ? `date_from=${dateFrom}` : "",
      dateTo ? `date_to=${dateTo}` : "",
    ]
      .filter(Boolean)
      .join("&");
    return request<ReconciliationReport>(
      `/admin/reconciliation${qs ? `?${qs}` : ""}`,
      { signal },
    );
  },
  retryEvent: (eventId: string) =>
    request<{ retried: string; event_type: string }>(
      `/admin/outbox/${eventId}/retry`,
      { method: "POST" },
    ),
};

export const partner = {
  listProperties: () => request<PropertyOut[]>("/partner/properties"),
  createProperty: (body: {
    name: string;
    property_type: PropertyType;
    city?: string;
  }) => request<PropertyOut>("/partner/properties", { method: "POST", body }),
  photos: {
    list: (propertyId: string, signal?: AbortSignal) =>
      request<Photo[]>(`/partner/properties/${propertyId}/photos`, { signal }),
    upload: (propertyId: string, file: File) => {
      const body = new FormData();
      body.append("file", file);
      return request<Photo[]>(`/partner/properties/${propertyId}/photos`, {
        method: "POST",
        body,
      });
    },
    remove: (propertyId: string, photoId: string) =>
      request<Photo[]>(`/partner/properties/${propertyId}/photos/${photoId}`, {
        method: "DELETE",
      }),
  },
  createUnitType: (body: {
    property_id: string;
    name: string;
    capacity: number;
    total_units: number;
    base_price: number;
  }) => request<UnitTypeOut>("/partner/unit-types", { method: "POST", body }),
  updateUnitType: (
    unitTypeId: string,
    body: { name?: string; capacity?: number; base_price?: number },
  ) =>
    request<UnitTypeOut>(`/partner/unit-types/${unitTypeId}`, {
      method: "PATCH",
      body,
    }),
  ratePlans: {
    list: (unitTypeId: string, signal?: AbortSignal) =>
      request<RatePlan[]>(
        `/partner/rate-plans?unit_type_id=${encodeURIComponent(unitTypeId)}`,
        { signal },
      ),
    create: (body: {
      unit_type_id: string;
      name: string;
      cancellation_policy: string;
    }) => request<RatePlan>("/partner/rate-plans", { method: "POST", body }),
  },
  prices: {
    set: (body: {
      rate_plan_id: string;
      date_from: string;
      date_to: string;
      price: number;
      min_stay: number;
    }) =>
      request<{ status: string }>("/partner/prices", { method: "POST", body }),
  },
  inventory: {
    close: (body: {
      unit_type_id: string;
      date_from: string;
      date_to: string;
      closed: boolean;
    }) =>
      request<{ affected: number }>("/partner/inventory/close", {
        method: "POST",
        body,
      }),
  },
  listUnitTypes: (propertyId: string, signal?: AbortSignal) =>
    request<UnitTypeOut[]>(`/partner/unit-types/property/${propertyId}`, {
      signal,
    }),
  calendar: (propertyId: string, dateFrom: string, dateTo: string) =>
    request<CalendarResponse>(
      `/partner/calendar?property_id=${encodeURIComponent(
        propertyId,
      )}&date_from=${toIsoDate(dateFrom)}&date_to=${toIsoDate(dateTo)}`,
    ),
  icalFeed: {
    get: (unitTypeId: string, signal?: AbortSignal) =>
      request<IcalFeed>(`/partner/unit-types/${unitTypeId}/ical-feed`, {
        signal,
      }),
    rotate: (unitTypeId: string) =>
      request<IcalFeed>(`/partner/unit-types/${unitTypeId}/ical-feed`, {
        method: "POST",
      }),
  },
  icalImport: {
    get: (unitTypeId: string, signal?: AbortSignal) =>
      request<IcalSubscription>(
        `/partner/unit-types/${unitTypeId}/ical-import`,
        { signal },
      ),
    set: (unitTypeId: string, url: string) =>
      request<IcalSubscription>(
        `/partner/unit-types/${unitTypeId}/ical-import`,
        { method: "PUT", body: { url } },
      ),
    remove: (unitTypeId: string) =>
      request<{ deleted: string }>(
        `/partner/unit-types/${unitTypeId}/ical-import`,
        { method: "DELETE" },
      ),
    sync: (unitTypeId: string) =>
      request<SyncResult>(
        `/partner/unit-types/${unitTypeId}/ical-import/sync`,
        { method: "POST" },
      ),
  },
  apiKeys: {
    list: (signal?: AbortSignal) =>
      request<ApiKeyOut[]>("/partner/api-keys", { signal }),
    create: (label: string) =>
      request<ApiKeyWithSecret>("/partner/api-keys", {
        method: "POST",
        body: { label },
      }),
    remove: (keyId: string) =>
      request<{ revoked: string }>(`/partner/api-keys/${keyId}`, {
        method: "DELETE",
      }),
  },
  webhooks: {
    list: (signal?: AbortSignal) =>
      request<WebhookOut[]>("/partner/webhooks", { signal }),
    create: (url: string, secret: string, eventTypes: string[]) =>
      request<WebhookOut>("/partner/webhooks", {
        method: "POST",
        body: { url, secret, event_types: eventTypes },
      }),
    remove: (webhookId: string) =>
      request<{ deleted: string }>(`/partner/webhooks/${webhookId}`, {
        method: "DELETE",
      }),
  },
  bookings: {
    list: (status: string | null, signal?: AbortSignal) => {
      const tail = status ? `?status=${encodeURIComponent(status)}` : "";
      return request<PartnerBookingOut[]>(`/bookings/partner/list${tail}`, {
        signal,
      });
    },
  },
};
