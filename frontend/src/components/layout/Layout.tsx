import { Outlet, useLocation } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { Header } from "./Header";

export function Layout() {
  const location = useLocation();

  return (
    <div className="min-h-screen" style={{ background: "var(--bg-page)" }}>
      <Sidebar />
      <div style={{ paddingLeft: "240px" }}>
        <Header />
        <main className="p-6 md:p-8">
          <div key={location.pathname} className="sk-page-enter">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
