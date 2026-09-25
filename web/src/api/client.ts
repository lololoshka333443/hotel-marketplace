/**
 * Thin typed fetch client for the API.
 *
 * All routes are under /v1 (proxied to FastAPI in dev, same origin in prod).
 * The token is read from localStorage; the auth endpoints don't need it.
 */

import type {
  ApiError,
  AuthMe,
  AvailabilityResponse,
  BookingOut,
  CalendarResponse,
  HoldConflict,
  HoldRequest,
  PropertyOut,
  PropertyPublic,
  PropertyType,
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
    method?: "GET" | "POST" | "PATCH" | "DELETE";
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
  if (options.body !== undefined) headers["Content-Type"] = "application/json";

  const response = await fetch(`${BASE}${path}`, {
    method: options.method ?? "GET",
    headers,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
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
  register: (email: string, password: string) =>
    request<TokenResponse>("/auth/register", {
      method: "POST",
      body: { email, password },
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
  list: (city?: string, signal?: AbortSignal) => {
    const qs = city ? `?city=${encodeURIComponent(city)}` : "";
    return request<PropertyPublic[]>(`/properties${qs}`, { signal });
  },
  get: (id: string, signal?: AbortSignal) =>
    request<PropertyPublic>(`/properties/${id}`, { signal }),
};

export const availability = {
  get: (unitTypeId: string, dateFrom: string, dateTo: string, signal?: AbortSignal) =>
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
      headers: idempotencyKey ? { "Idempotency-Key": idempotencyKey } : undefined,
    }),
  get: (id: string, signal?: AbortSignal) =>
    request<BookingOut>(`/bookings/${id}`, { signal }),
  pay: (id: string) => request<BookingOut>(`/bookings/${id}/pay`, { method: "POST" }),
  cancel: (id: string) =>
    request<BookingOut>(`/bookings/${id}/cancel`, { method: "POST" }),
};

// ---- partner --------------------------------------------------------------

export const partner = {
  listProperties: () => request<PropertyOut[]>("/partner/properties"),
  createProperty: (body: {
    name: string;
    property_type: PropertyType;
    city?: string;
  }) =>
    request<PropertyOut>("/partner/properties", { method: "POST", body }),
  listUnitTypes: (propertyId: string) =>
    request<UnitTypeOut[]>(`/partner/unit-types/property/${propertyId}`),
  calendar: (propertyId: string, dateFrom: string, dateTo: string) =>
    request<CalendarResponse>(
      `/partner/calendar?property_id=${encodeURIComponent(
        propertyId,
      )}&date_from=${toIsoDate(dateFrom)}&date_to=${toIsoDate(dateTo)}`,
    ),
};
