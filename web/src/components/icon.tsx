// Lucide SVG geometry, ISC/MIT. License: public/icons/lucide/LICENSE.
export default function Icon({ name, className = "" }: { name: "search" | "map-pin" | "clock" | "arrow-up-right"; className?: string }) {
  return <svg className={`ui-icon ${className}`} width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
    {name === "search" && <><path d="m21 21-4.34-4.34" /><circle cx="11" cy="11" r="8" /></>}
    {name === "map-pin" && <><path d="M20 10c0 4.993-5.539 10.193-7.399 11.799a1 1 0 0 1-1.202 0C9.539 20.193 4 14.993 4 10a8 8 0 0 1 16 0" /><circle cx="12" cy="10" r="3" /></>}
    {name === "clock" && <><circle cx="12" cy="12" r="10" /><path d="M12 6v6l4 2" /></>}
    {name === "arrow-up-right" && <><path d="M7 7h10v10" /><path d="M7 17 17 7" /></>}
  </svg>;
}
