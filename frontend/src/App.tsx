import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Layout } from "@/components/layout/Layout";
import Dashboard from "@/pages/Dashboard";
import IndexPage from "@/pages/IndexPage";
import SearchPage from "@/pages/SearchPage";
import AskPage from "@/pages/AskPage";
import VoicePage from "@/pages/VoicePage";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/index" element={<IndexPage />} />
          <Route path="/search" element={<SearchPage />} />
          <Route path="/ask" element={<AskPage />} />
          <Route path="/voice" element={<VoicePage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
