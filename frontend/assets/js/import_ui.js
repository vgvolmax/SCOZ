((root) => {
  "use strict";

  const sources = Object.freeze({
    ozon_products: Object.freeze({ label: "Товары на Ozon", pattern: "analytics_report_*.xlsx", prefix: "analytics_report" }),
    search_visibility: Object.freeze({ label: "Поисковая видимость Ozon", pattern: "explainer_report_*.xlsx", prefix: "explainer_report" }),
    seller_queries: Object.freeze({ label: "Запросы моего товара", pattern: "seller-queries_*.xlsx", prefix: "seller-queries" }),
    query_metrics: Object.freeze({ label: "Метрики поисковых запросов", pattern: "queries_report*.xlsx", prefix: "queries_report" }),
  });

  function classifyFilename(expectedSource, filename) {
    const normalized = String(filename || "").toLocaleLowerCase();
    const detected = Object.entries(sources).find(([, definition]) => normalized.startsWith(definition.prefix));
    if (!detected) return { kind: "UNKNOWN" };
    if (detected[0] === expectedSource) return { kind: "MATCH" };
    return { kind: "KNOWN_OTHER", detectedSource: detected[0] };
  }

  function formatElapsed(seconds) {
    const wholeSeconds = Math.max(0, Math.floor(Number(seconds) || 0));
    const minutes = Math.floor(wholeSeconds / 60);
    return `${String(minutes).padStart(2, "0")}:${String(wholeSeconds % 60).padStart(2, "0")}`;
  }

  function workingMessage(seconds) {
    const elapsed = formatElapsed(seconds);
    return seconds >= 30
      ? `Импорт занимает больше обычного, обработка продолжается · ${elapsed}`
      : `Импортируем… ${elapsed}`;
  }

  root.ScozImportUi = Object.freeze({ sources, classifyFilename, formatElapsed, workingMessage });
})(typeof window === "undefined" ? globalThis : window);
