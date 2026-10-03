import { HomePage } from "@/pages/HomePage";
import { SearchPage } from "@/pages/SearchPage";
import { PropertyPage } from "@/pages/PropertyPage";
import { CheckoutPage } from "@/pages/CheckoutPage";
import { BookingSuccessPage } from "@/pages/BookingSuccessPage";
import { LoginPage } from "@/pages/auth/LoginPage";
import { RegisterPage } from "@/pages/auth/RegisterPage";
import { ComponentsPage } from "@/pages/ComponentsPage";
import { PartnerLayout } from "@/pages/partner/PartnerLayout";
import { PartnerDashboardPage } from "@/pages/partner/PartnerDashboardPage";
import { PartnerCalendarPage } from "@/pages/partner/PartnerCalendarPage";
import { PartnerBookingsPage } from "@/pages/partner/PartnerBookingsPage";

import { AdminLayout } from "@/pages/admin/AdminLayout";
import { AdminLoginPage } from "@/pages/admin/AdminLoginPage";
import { AdminReportsPage } from "@/pages/admin/AdminReportsPage";
import { AdminModerationPage } from "@/pages/admin/AdminModerationPage";
import { AdminOutboxPage } from "@/pages/admin/AdminOutboxPage";
import { AdminReconciliationPage } from "@/pages/admin/AdminReconciliationPage";
import { NotFoundPage } from "@/pages/NotFoundPage";
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
      { path: "booking/:bookingId/success", element: <BookingSuccessPage /> },
      { path: "login", element: <LoginPage /> },
      // Reachable from the login page; without this the link 404s.
      { path: "register", element: <RegisterPage /> },
      // States harness for the base components - gate/visual review only.
      { path: "components", element: <ComponentsPage /> },
      {
        path: "partner",
        element: <PartnerLayout />,
        children: [
          { index: true, element: <PartnerDashboardPage /> },
          { path: "calendar", element: <PartnerCalendarPage /> },
          { path: "bookings", element: <PartnerBookingsPage /> },
        ],
      },
      { path: "admin/login", element: <AdminLoginPage /> },
      {
        path: "admin",
        element: <AdminLayout />,
        children: [
          { index: true, element: <AdminReportsPage /> },
          { path: "moderation", element: <AdminModerationPage /> },
          { path: "outbox", element: <AdminOutboxPage /> },
          { path: "reconciliation", element: <AdminReconciliationPage /> },
        ],
      },
      // The SPA fallback serves index.html on any URL, so an unknown path still
      // runs the app - it needs a real screen, not a blank one.
      { path: "*", element: <NotFoundPage /> },
    ],
  },
];
