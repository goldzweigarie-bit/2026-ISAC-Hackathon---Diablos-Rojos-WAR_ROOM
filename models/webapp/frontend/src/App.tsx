import { NavLink, Route, Routes } from "react-router-dom";
import { Diablo } from "./components/Diablo";
import { BullpenDrawer } from "./components/BullpenDrawer";
import { useLang } from "./i18n";
import { useAppState } from "./state";
import Home from "./pages/Home";
import StadiumPage from "./pages/StadiumPage";
import PitcherPage from "./pages/PitcherPage";
import FreeAgentsPage from "./pages/FreeAgentsPage";
import MethodologyPage from "./pages/MethodologyPage";

export default function App() {
  const { t, lang, setLang } = useLang();
  const { meta, bullpenOpen, setBullpenOpen } = useAppState();
  return (
    <>
      <header className="topbar">
        <NavLink to="/" className="brand" aria-label={t("appName")}>
          <Diablo size={30} still />
          <span>Diablos Stuff<span className="plus">+</span></span>
        </NavLink>
        <nav className="nav">
          <NavLink to="/" end>{t("navMap")}</NavLink>
          <NavLink to="/agentes-libres">{t("navFreeAgents")}</NavLink>
          <NavLink to="/metodologia">{t("navMethod")}</NavLink>
        </nav>
        <div className="spacer" />
        {meta?.model === "placeholder" && <span className="chip gold">{t("placeholderModel")}</span>}
        <div className="lang-toggle" role="group" aria-label="Language">
          <button className={lang === "es" ? "on" : ""} onClick={() => setLang("es")}>ES</button>
          <button className={lang === "en" ? "on" : ""} onClick={() => setLang("en")}>EN</button>
        </div>
      </header>
      {meta?.synthetic && <div className="banner">{t("syntheticBanner")}</div>}
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/estadio/:id" element={<StadiumPage />} />
        <Route path="/lanzador/:id" element={<PitcherPage />} />
        <Route path="/agentes-libres" element={<FreeAgentsPage />} />
        <Route path="/metodologia" element={<MethodologyPage />} />
      </Routes>
      <button className="diablo-btn" onClick={() => setBullpenOpen(true)} aria-label={t("bullpenTitle")}>
        <span className="diablo-bubble">{t("diabloHint")}</span>
        <Diablo size={92} />
      </button>
      {bullpenOpen && <BullpenDrawer onClose={() => setBullpenOpen(false)} />}
    </>
  );
}
