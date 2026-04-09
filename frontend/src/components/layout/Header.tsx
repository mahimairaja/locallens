import { useLocation } from "react-router-dom";

const pageTitles: Record<string, string> = {
  "/": "Dashboard",
  "/index": "Index Files",
  "/search": "Search",
  "/ask": "Ask",
  "/voice": "Voice",
};

export function Header() {
  const location = useLocation();
  const title = pageTitles[location.pathname] ?? "LocalLens";

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center border-b border-border bg-background/80 px-6 backdrop-blur-sm">
      <h1 className="text-lg font-semibold text-foreground">{title}</h1>
    </header>
  );
}
