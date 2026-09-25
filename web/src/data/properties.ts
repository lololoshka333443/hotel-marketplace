/**
 * Real property data — hotels "Выше неба" & "Седьмое небо" in Koktebel.
 *
 * Source: the partner's own landing page (AboveTheSky). Names, room titles,
 * capacities and photo sets are real. Prices come from rate plans, not here —
 * this file only carries catalog/visual data.
 *
 * Photos are pre-optimized WebP under web/public/rooms/<n>/ (see scripts/optimize_photos.py).
 */

import type { PropertyType } from "@/api/types";

export interface RoomPhoto {
  src: string;
  alt: string;
}

export interface RoomData {
  /** Room number as shown to guests, e.g. "Номер 1". */
  title: string;
  /** Type of room (family, sea view…). */
  subtitle: string;
  capacity: number;
  badge: string;
  cover: string;
  gallery: RoomPhoto[];
}

export interface PropertySeed {
  name: string;
  city: string;
  propertyType: PropertyType;
  address: string;
  rooms: RoomData[];
  amenities: string[];
}

const rooms = (n: number, files: string[]): RoomPhoto[] =>
  files.map((f) => ({ src: `/rooms/${n}/${f}`, alt: `Номер ${n} — фото` }));

const COVERS = {
  1: "/rooms/1/IMG_0062.webp",
  2: "/rooms/2/IMG_0117.webp",
  3: "/rooms/3/photo_5298498534154293983_y.webp",
  4: "/rooms/4/IMG_1859.webp",
  5: "/rooms/5/IMG_0023.webp",
  6: "/rooms/6/IMG_E7590.webp",
} as const;

const AMENITIES = [
  "Парковка",
  "Wi-Fi",
  "Зона барбекю",
  "Батут для детей",
  "Прачечная",
  "Кухня в номере",
  "Кондиционер",
  "ЖК-телевизор",
  "Постельное бельё и полотенца",
  "Видеонаблюдение 24/7",
];

export const PROPERTIES: PropertySeed[] = [
  {
    name: "Выше неба",
    city: "Коктебель",
    propertyType: "hotel",
    address: "Коктебель, Полевая улица",
    rooms: [
      {
        title: "Номер 1",
        subtitle: "Семейный номер с видом на горы и террасой",
        capacity: 4,
        badge: "Терраса",
        cover: COVERS[1],
        gallery: rooms(1, [
          "IMG_0062.webp",
          "IMG_0064.webp",
          "IMG_0067.webp",
          "IMG_0077.webp",
        ]),
      },
      {
        title: "Номер 2",
        subtitle: "Семейный номер с видом на горы и террасой",
        capacity: 4,
        badge: "Терраса",
        cover: COVERS[2],
        gallery: rooms(2, [
          "IMG_0117.webp",
          "IMG_0129.webp",
          "IMG_0136.webp",
          "IMG_0141.webp",
        ]),
      },
    ],
    amenities: AMENITIES,
  },
  {
    name: "Седьмое небо",
    city: "Коктебель",
    propertyType: "hotel",
    address: "Коктебель, Полевая улица",
    rooms: [
      {
        title: "Номер 3",
        subtitle: "Номер с видом на море и горы",
        capacity: 4,
        badge: "Вид на море",
        cover: COVERS[3],
        gallery: rooms(3, [
          "photo_5298498534154293983_y.webp",
          "photo_5298498534154293968_y.webp",
          "photo_5298498534154293951_y.webp",
          "TABQ5289.webp",
        ]),
      },
      {
        title: "Номер 4",
        subtitle: "Номер с террасой и видом на горы",
        capacity: 4,
        badge: "Терраса",
        cover: COVERS[4],
        gallery: rooms(4, [
          "IMG_1859.webp",
          "IMG_2940.webp",
          "IMG_1862.webp",
          "IMG_1787.webp",
        ]),
      },
      {
        title: "Номер 5",
        subtitle: "Номер с видом на море, горы и Коктебель",
        capacity: 4,
        badge: "Вид на море",
        cover: COVERS[5],
        gallery: rooms(5, [
          "IMG_0023.webp",
          "IMG_0047.webp",
          "IMG_0020.webp",
          "IMG_1878.webp",
        ]),
      },
      {
        title: "Номер 6",
        subtitle: "Номер с балконом и видом на горы",
        capacity: 4,
        badge: "Вид на горы",
        cover: COVERS[6],
        gallery: rooms(6, [
          "IMG_E7590.webp",
          "IMG_5242.webp",
        ]),
      },
    ],
    amenities: AMENITIES,
  },
];

export const CONTACT = {
  phone: "+7 911 446-13-75",
  email: "kviki35@mail.ru",
  telegram: "@yourhotel",
  hours: "Ежедневно 09:00–20:00 (МСК)",
};
