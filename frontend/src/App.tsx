import { BrowserRouter, Routes, Route } from "react-router-dom";

import Navbar from "./components/Navbar";
import { FlyerProvider } from "./context/FlyerContext";
import CreateFlyer from "./pages/CreateFlyer";
import EditTemplate from "./pages/EditTemplate";

export default function App() {
  return (
    <BrowserRouter>
      <FlyerProvider>
        <div style={{ display: "flex", flexDirection: "column", height: "100vh" }}>
          <Navbar />
          <div style={{ flex: 1, overflow: "auto" }}>
            <Routes>
              <Route path="/" element={<CreateFlyer />} />
              <Route path="/edit-template" element={<EditTemplate />} />
            </Routes>
          </div>
        </div>
      </FlyerProvider>
    </BrowserRouter>
  );
}
