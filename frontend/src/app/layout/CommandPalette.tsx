import * as Dialog from "@radix-ui/react-dialog";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router";

import { Icon } from "./icons";
import { destinations } from "./nav-items";

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const navigate = useNavigate();
  useEffect(() => {
    const handleKey = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen(true);
      }
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, []);
  const matches = useMemo(
    () =>
      destinations.filter((item) => item.label.toLowerCase().includes(query.trim().toLowerCase())),
    [query],
  );
  const go = (to: string) => {
    void navigate(to);
    setOpen(false);
    setQuery("");
  };
  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Portal>
        <div aria-hidden="true" className="dialog-scrim" />
        <Dialog.Content className="command-dialog" aria-describedby={undefined}>
          <div className="command-heading">
            <Dialog.Title>Go somewhere</Dialog.Title>
            <Dialog.Close className="icon-button" aria-label="Close command palette">
              <Icon name="close" />
            </Dialog.Close>
          </div>
          <label className="command-search">
            <span className="visually-hidden">Find a page</span>
            <Icon name="search" />
            <input
              aria-label="Find a page"
              autoFocus
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Type a page name"
              role="combobox"
              value={query}
            />
            <kbd>Esc</kbd>
          </label>
          <div className="command-results" role="listbox" aria-label="Pages">
            {matches.map((item) => (
              <button key={item.to} onClick={() => go(item.to)} role="option">
                <Icon name={item.icon} />
                <span>{item.label}</span>
                <Icon className="command-arrow" name="arrow" />
              </button>
            ))}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
