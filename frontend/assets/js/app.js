(() => {
  "use strict";
  const copy = {
    products: ["Товары", "Здесь появятся ваши товары после добавления данных.", "Пока нет данных", "Начните работу в разделе «Данные». Содержимое появится здесь после настройки."],
    data: ["Данные", "Управляйте источниками данных SCOZ.", "Данные ещё не добавлены", "В следующих версиях здесь появятся доступные способы добавления данных."],
    settings: ["Настройки", "Параметры локального приложения.", "Настройки пока не требуются", "SCOZ готов к работе с базовыми параметрами."]
  };
  const buttons = [...document.querySelectorAll(".nav-item")];
  const title = document.querySelector("#page-title");
  const description = document.querySelector("#page-description");
  const emptyTitle = document.querySelector("#empty-title");
  const emptyDescription = document.querySelector("#empty-description");
  buttons.forEach((button) => button.addEventListener("click", () => {
    buttons.forEach((item) => { item.classList.remove("is-active"); item.removeAttribute("aria-current"); });
    button.classList.add("is-active"); button.setAttribute("aria-current", "page");
    [title.textContent, description.textContent, emptyTitle.textContent, emptyDescription.textContent] = copy[button.dataset.section];
    document.querySelector(".content").focus();
  }));
})();
