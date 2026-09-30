import { NavLink } from "react-router";

import { Icon } from "./icons";
import { destinations } from "./nav-items";

export function PrimaryNav() {
  return (
    <nav aria-label="Primary" className="primary-nav">
      {destinations.map((destination, index) => (
        <NavLink
          aria-label={destination.label}
          className={({ isActive }) => `nav-link${isActive ? " nav-link--active" : ""}`}
          key={destination.to}
          to={destination.to}
        >
          <span
            className="nav-folio"
            aria-hidden="true"
            data-folio={String(index + 1).padStart(2, "0")}
          />
          <Icon name={destination.icon} />
          <span>{destination.label}</span>
        </NavLink>
      ))}
    </nav>
  );
}
