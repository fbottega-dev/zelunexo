(() => {
  "use strict";
  const printButton = document.getElementById("print-report");
  printButton.hidden = false;
  printButton.addEventListener("click", () => window.print());
  const groups = [...document.querySelectorAll(".duplicate-group")];
  const allDetails = [...document.querySelectorAll("details")];
  let printState = [];
  window.addEventListener("beforeprint", () => {
    printState = allDetails.map((detail) => ({
      detail,
      open: detail.open,
      hidden: detail.hidden,
    }));
    allDetails.forEach((detail) => {
      detail.open = true;
      detail.hidden = false;
    });
  });
  window.addEventListener("afterprint", () => {
    printState.forEach(({ detail, open, hidden }) => {
      detail.open = open;
      detail.hidden = hidden;
    });
    printState = [];
  });
  if (!groups.length) return;
  const search = document.getElementById("file-search");
  const filter = document.getElementById("group-filter");
  const clear = document.getElementById("clear-search");
  const count = document.getElementById("result-count");
  const expand = document.getElementById("expand-all");
  const collapse = document.getElementById("collapse-all");
  const normalize = (value) =>
    value
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLocaleLowerCase("pt-BR");
  const paths = new Map(
    groups.map((group) => [
      group,
      normalize(group.querySelector(".file-list").textContent),
    ]),
  );
  function updateButtons() {
    const visible = groups.filter((group) => !group.hidden);
    expand.disabled =
      visible.length === 0 || visible.every((group) => group.open);
    collapse.disabled =
      visible.length === 0 || visible.every((group) => !group.open);
  }
  function update() {
    const query = normalize(search.value.trim());
    let visible = 0;
    groups.forEach((group) => {
      const matches =
        paths.get(group).includes(query) &&
        (filter.value === "all" || Number(group.dataset.files) >= 3);
      group.hidden = !matches;
      if (matches) visible += 1;
    });
    clear.hidden = !search.value;
    count.textContent = `${visible} de ${groups.length} ${groups.length === 1 ? "grupo exibido" : "grupos exibidos"}`;
    document.getElementById("no-results").hidden = visible !== 0;
    updateButtons();
  }
  search.addEventListener("input", update);
  filter.addEventListener("change", update);
  clear.addEventListener("click", () => {
    search.value = "";
    update();
    search.focus();
  });
  expand.addEventListener("click", () => {
    groups
      .filter((group) => !group.hidden)
      .forEach((group) => {
        group.open = true;
      });
    updateButtons();
  });
  collapse.addEventListener("click", () => {
    groups
      .filter((group) => !group.hidden)
      .forEach((group) => {
        group.open = false;
      });
    updateButtons();
  });
  groups.forEach((group) => group.addEventListener("toggle", updateButtons));
  document.getElementById("group-tools").hidden = false;
  document.getElementById("results-toolbar").hidden = false;
  update();
})();
