import { useState } from "react";
import { Navigate, Outlet, RouterProvider, createBrowserRouter, createMemoryRouter, type RouteObject } from "react-router";

import { AppShell } from "./layout/AppShell";
import { FrameworkMapPage } from "../features/framework-map/FrameworkMapPage";
import { DashboardPage } from "../features/dashboard/DashboardPage";
import { LibraryPage } from "../features/libraries/LibraryPage";
import { SettingsPage } from "../features/settings/SettingsPage";
import { TrackerPage } from "../features/tracker/TrackerPage";
import { LoginPage } from "../features/auth/LoginPage";
import { useSession } from "./session/session-context";

function ShellRoute() {
  const { status } = useSession();
  if (status === "loading") return <div className="session-loading" role="status">Loading workspace…</div>;
  if (status === "unauthenticated") return <Navigate replace to="/login" />;
  return <AppShell><Outlet /></AppShell>;
}

const routes: RouteObject[] = [
  { path: "/login", element: <LoginPage /> },
  {
    element: <ShellRoute />,
    children: [
      { index: true, element: <Navigate replace to="/dashboard" /> },
      { path: "/dashboard", element: <DashboardPage /> },
      { path: "/frameworks/:framework/map", element: <FrameworkMapPage /> },
      { path: "/tracker", element: <TrackerPage /> },
      { path: "/documents", element: <LibraryPage kind="documents" /> },
      { path: "/evidence", element: <LibraryPage kind="evidence" /> },
      { path: "/settings", element: <SettingsPage /> },
      { path: "*", element: <Navigate replace to="/dashboard" /> },
    ],
  },
];

export function AppRouter({ initialEntries }: { initialEntries?: string[] }) {
  const [router] = useState(() =>
    initialEntries ? createMemoryRouter(routes, { initialEntries }) : createBrowserRouter(routes),
  );
  return <RouterProvider router={router} />;
}
