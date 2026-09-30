import type { ReactNode, SVGProps } from "react";

export type IconName =
  | "dashboard"
  | "map"
  | "tracker"
  | "documents"
  | "evidence"
  | "settings"
  | "search"
  | "close"
  | "arrow";

const paths: Record<IconName, ReactNode> = {
  dashboard: <><path d="M4 4h6v6H4zM14 4h6v4h-6zM14 12h6v8h-6zM4 14h6v6H4z" /></>,
  map: <><path d="m3 6 5-2 8 3 5-2v13l-5 2-8-3-5 2zM8 4v13M16 7v13" /></>,
  tracker: <><path d="M5 6h14M5 12h14M5 18h14M8 4v16" /></>,
  documents: <><path d="M6 3h8l4 4v14H6zM14 3v5h5M9 12h6M9 16h6" /></>,
  evidence: <><path d="M4 5h16v14H4zM8 9h8M8 13h5M8 17h3" /></>,
  settings: <><circle cx="12" cy="12" r="3" /><path d="M19 12a7 7 0 0 0-.1-1l2-1.5-2-3.4-2.4 1A7 7 0 0 0 15 6l-.3-2.6h-4L10.4 6A7 7 0 0 0 8.8 7L6.5 6.1l-2 3.4 2 1.5a7 7 0 0 0 0 2l-2 1.5 2 3.4 2.3-1A7 7 0 0 0 10.4 18l.3 2.6h4L15 18a7 7 0 0 0 1.6-1.1l2.4 1 2-3.4-2-1.5a7 7 0 0 0 .1-1Z" /></>,
  search: <><circle cx="10.5" cy="10.5" r="6.5" /><path d="m16 16 5 5" /></>,
  close: <><path d="m6 6 12 12M18 6 6 18" /></>,
  arrow: <><path d="M5 12h14M14 7l5 5-5 5" /></>,
};

export function Icon({ name, ...props }: { name: IconName } & SVGProps<SVGSVGElement>) {
  return (
    <svg
      aria-hidden="true"
      fill="none"
      height="20"
      viewBox="0 0 24 24"
      width="20"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="1.6"
      {...props}
    >
      {paths[name]}
    </svg>
  );
}
