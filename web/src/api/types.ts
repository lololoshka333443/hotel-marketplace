/**
 * TypeScript types mirroring the backend Pydantic schemas.
 *
 * Source of truth: app/modules/<module>/schemas.py. When a schema changes on the
 * backend, update it here too. Types are deliberately exact (no unions the
 * backend does not produce) so mistakes surface at compile time.
 *
 * Notes on tricky fields:
 *  - checkin_time/checkout_time are Python `datetime.time` → serialized as
 *    "HH:MM:SS" strings. Parse, do not feed them to `new Date()`.
 *  - id fields are Postgres uuid, returned as text. Never Number()-cast.
 *  - address is free-form JSONB; may be `{}`.
 */

export type PropertyType = "hotel" | "apartment" | "house" | "room" | "hostel";
export type PropertyStatus = "draft" | "pending_moderation" | "published" | "blocked";
export type BookingStatus =
  | "hold"
  | "paid"
  | "confirmed"
  | "cancelled"
  | "failed"
  | "conflict"
  | "no_show"
  | "refunded";

/** "HH:MM:SS" from the backend's datetime.time. */
export type TimeString = string;

export interface Address {
  street?: string;
  city?: string;
  settlement?: string;
  district?: string;
  region?: string;
  postal_code?: string;
  house_number?: string;
  building?: string;
  apartment?: string;
  [key: string]: string | undefined;
}

/** Public catalog item - GET /v1/properties. */
export interface PropertyPublic {
  id: string;
  name: string;
  slug: string | null;
  property_type: PropertyType;
  city: string;
  timezone: string;
  checkin_time: TimeString;
  checkout_time: TimeString;
  currency: string;
  lat: number | null;
  lng: number | null;
  address: Address;
  /** Photo URLs - the largest first. Empty until photos land on the backend. */
  photos?: string[];
}

export interface PropertyOut extends PropertyPublic {
  id: string;
  partner_id: string;
  status: PropertyStatus;
  created_at: string;
}

export interface UnitTypeOut {
  id: string;
  property_id: string;
  name: string;
  capacity: number;
  total_units: number;
}

export interface GuestInfo {
  name: string;
  email: string;
  phone: string;
}

export interface HoldRequest {
  unit_type_id: string;
  checkin: string; // ISO date "YYYY-MM-DD"
  checkout: string; // ISO date "YYYY-MM-DD"
  guest: GuestInfo;
}

export interface BookingLineOut {
  date: string; // ISO date
  price: number;
}

export interface BookingOut {
  id: string;
  code: string;
  status: BookingStatus;
  total_amount: number;
  hold_expires_at: string | null; // ISO datetime, null unless status === "hold"
  checkin_date: string;
  checkout_date: string;
  lines: BookingLineOut[];
}

export interface AvailabilityDay {
  date: string; // ISO date
  available: boolean;
  price: number | null;
  closed: boolean;
}

/** One cell of the partner chessboard. */
export interface CalendarDay {
  date: string;
  available: number;
  hold: number;
  sold: number;
  free: number;
  closed: boolean;
  price: number;
  min_stay: number;
}

export interface CalendarUnit {
  unit_type_id: string;
  unit_type_name: string;
  property_id: string;
  property_name: string;
  total_units: number;
  rate_plan_id: string | null;
  days: CalendarDay[];
}

export interface CalendarResponse {
  date_from: string;
  date_to: string;
  units: CalendarUnit[];
}

export interface AvailabilityResponse {
  unit_type_id: string;
  date_from: string;
  date_to: string;
  days: AvailabilityDay[];
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface AuthMe {
  partner_id: string;
  scope: string;
}

export interface HoldConflict {
  detail: string;
  reason: "not_available" | "conflict";
}

export interface ApiError {
  detail: string;
  reason?: string;
}
