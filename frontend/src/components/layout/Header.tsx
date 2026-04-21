import { useLocation } from "react-router-dom";

const pageTitles: Record<string, string> = {
  "/": "Dashboard",
  "/index": "Indexing",
  "/search": "Search",
  "/ask": "Ask",
  "/stack": "Under the Hood",
  "/settings": "Settings",
  "/audit": "Audit Log",
};

export function Header() {
  const location = useLocation();
  const title = pageTitles[location.pathname] ?? "LocalLens";

  return (
    <header className="sk-header">
      <h1>{title}</h1>
    </header>
  );
}
