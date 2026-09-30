import { QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

import { createQueryClient } from "./app/query-client";
import { AppRouter } from "./app/router";
import { SessionProvider } from "./app/session/SessionProvider";

export function App({ initialEntries }: { initialEntries?: string[] }) {
  const [queryClient] = useState(createQueryClient);
  return (
    <QueryClientProvider client={queryClient}>
      <SessionProvider><AppRouter initialEntries={initialEntries} /></SessionProvider>
    </QueryClientProvider>
  );
}
