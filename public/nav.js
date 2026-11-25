(() => {
  const pages = ["claim", "stock", "schemes", "supply", "digest"];
  function show(p) {
    if (!pages.includes(p)) p = "claim";
    document.querySelectorAll(".navtab").forEach((b) => b.classList.toggle("on", b.dataset.page === p));
    pages.forEach((k) => (document.getElementById("p-" + k).hidden = k !== p));
  }
  document.querySelectorAll(".navtab").forEach((b) => b.addEventListener("click", () => { location.hash = b.dataset.page === "claim" ? "" : b.dataset.page; show(b.dataset.page); }));
  window.addEventListener("hashchange", () => show(location.hash.slice(1)));
  show(location.hash.slice(1));
})();
