import { useState } from "react";

const sections = ["Товары", "Данные", "Настройки"] as const;
type Section = (typeof sections)[number];

const descriptions: Record<Section, string> = {
  "Товары": "Список товаров пока пуст.",
  "Данные": "Данные пока не добавлены.",
  "Настройки": "Настройки появятся по мере подключения возможностей SCOZ."
};

export function App() {
  const [active, setActive] = useState<Section>("Товары");
  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><span className="brand-mark" aria-hidden="true">S</span><span>SCOZ</span></div>
      <nav className="navigation" aria-label="Основная навигация">
        {sections.map(section => <button key={section} type="button"
          className={active === section ? "nav-item is-active" : "nav-item"}
          aria-current={active === section ? "page" : undefined} onClick={() => setActive(section)}>{section}</button>)}
      </nav>
    </aside>
    <main className="main-content"><header><p className="eyebrow">Рабочее пространство</p><h1>{active}</h1></header>
      <section className="empty-state" aria-live="polite"><h2>{descriptions[active]}</h2><p>SCOZ готов к работе. Возможности будут доступны в следующих версиях.</p></section>
    </main>
  </div>;
}
