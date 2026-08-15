import { useState } from 'react'

const sections = ['Товары', 'Данные', 'Настройки'] as const

export default function App() {
  const [active, setActive] = useState<(typeof sections)[number]>('Товары')
  return <div className="shell">
    <header className="topbar"><a className="brand" href="#main" aria-label="SCOZ — к содержимому">SCOZ</a>
      <nav aria-label="Основная навигация">{sections.map(section => <button key={section} className={active === section ? 'nav-item active' : 'nav-item'} aria-current={active === section ? 'page' : undefined} onClick={() => setActive(section)}>{section}</button>)}</nav>
    </header>
    <main id="main" tabIndex={-1}>
      <div className="page-heading"><p className="eyebrow">Рабочая область</p><h1>{active}</h1><p>Локальное приложение для анализа карточек Ozon.</p></div>
      <section className="empty" aria-labelledby="empty-title"><div className="empty-icon" aria-hidden="true">S</div><h2 id="empty-title">Здесь пока нет данных</h2><p>Функции работы с данными появятся на следующих этапах разработки SCOZ.</p></section>
    </main>
  </div>
}
