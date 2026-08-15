import { useState } from "react";

const sections = ["Товары", "Данные", "Настройки"] as const;

export function App() {
  const [active, setActive] = useState<(typeof sections)[number]>("Товары");
  return <div className="app-shell">
    <aside className="sidebar" aria-label="Основная навигация">
      <div className="brand">SCOZ</div>
      <nav>{sections.map(section => <button key={section} type="button"
        className={active === section ? "nav-item is-active" : "nav-item"}
        aria-current={active === section ? "page" : undefined}
        onClick={() => setActive(section)}>{section}</button>)}</nav>
    </aside>
    <main className="main-content"><header><p className="eyebrow">Рабочее пространство</p><h1>{active}</h1></header>
      <section className="empty-state"><h2>Раздел готов к работе</h2><p>Данные для этого раздела пока не загружены.</p></section>
    </main>
  </div>;
}
