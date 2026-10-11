import { FreeAgentTable } from "../components/FreeAgentTable";
import { useLang } from "../i18n";

export default function FreeAgentsPage() {
  const { t } = useLang();
  return (
    <main className="page">
      <div className="eyebrow">Harp Helú · 2,232 m</div>
      <h1>{t("faTitle")}</h1>
      <p className="muted" style={{ marginTop: 6 }}>{t("faHint")}</p>
      <section className="panel" style={{ marginTop: 16 }}><FreeAgentTable /></section>
    </main>
  );
}
