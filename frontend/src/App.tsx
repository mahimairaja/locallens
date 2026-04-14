import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Layout } from "@/components/layout/Layout";
import Dashboard from "@/pages/Dashboard";
import IndexPage from "@/pages/IndexPage";
import SearchPage from "@/pages/SearchPage";
import AskPage from "@/pages/AskPage";
import StackPage from "@/pages/StackPage";
import SettingsPage from "@/pages/SettingsPage";
import AuditPage from "@/pages/AuditPage";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/index" element={<IndexPage />} />
          <Route path="/search" element={<SearchPage />} />
          <Route path="/ask" element={<AskPage />} />
          <Route path="/stack" element={<StackPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/audit" element={<AuditPage />} />
          {/* Voice is now merged into /ask -- keep /voice pointing there for
              anyone who bookmarked the old route. */}
          <Route path="/voice" element={<Navigate to="/ask" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
