import type { IconName } from "./icons";

export const destinations: { label: string; to: string; icon: IconName }[] = [
  { label: "Dashboard", to: "/dashboard", icon: "dashboard" },
  { label: "Framework map", to: "/frameworks/soc2/map", icon: "map" },
  { label: "Tracker", to: "/tracker", icon: "tracker" },
  { label: "Documents", to: "/documents", icon: "documents" },
  { label: "Evidence", to: "/evidence", icon: "evidence" },
  { label: "Settings", to: "/settings", icon: "settings" },
];
