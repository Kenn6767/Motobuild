document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-modal]").forEach(button => {
    button.addEventListener("click", () => document.getElementById(button.dataset.modal)?.showModal());
  });
  document.querySelectorAll("[data-close]").forEach(button => {
    button.addEventListener("click", () => button.closest("dialog")?.close());
  });
  document.querySelectorAll("dialog").forEach(dialog => {
    dialog.addEventListener("click", event => {
      if (event.target === dialog) dialog.close();
    });
  });
  document.querySelectorAll(".flash").forEach(flash => {
    window.setTimeout(() => { flash.classList.add("fade-out"); }, 5500);
  });
});