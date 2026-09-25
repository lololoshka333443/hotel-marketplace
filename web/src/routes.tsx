import { HomePage } from "@/pages/HomePage";
import { SearchPage } from "@/pages/SearchPage";
import { PropertyPage } from "@/pages/PropertyPage";
import { CheckoutPage } from "@/pages/CheckoutPage";
import { LoginPage } from "@/pages/auth/LoginPage";
import { PartnerLayout } from "@/pages/partner/PartnerLayout";
import { PartnerDashboardPage } from "@/pages/partner/PartnerDashboardPage";
import { PartnerCalendarPage } from "@/pages/partner/PartnerCalendarPage";
import type { RouteObject } from "react-router-dom";

import { AppLayout } from "@/components/AppLayout";

export const routes: RouteObject[] = [
  {
    path: "/",
    element: <AppLayout />,
    children: [
      { index: true, element: <HomePage /> },
      { path: "search", element: <SearchPage /> },
      { path: "property/:id", element: <PropertyPage /> },
      { path: "checkout/:bookingId", element: <CheckoutPage /> },
      { path: "login", element: <LoginPage /> },
      {
        path: "partner",
        element: <PartnerLayout />,
        children: [
          { index: true, element: <PartnerDashboardPage /> },
          { path: "calendar", element: <PartnerCalendarPage /> },
        ],
      },
    ],
  },
];
