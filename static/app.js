// Автодополнение запроса и счётчик слов (лимит — 15 слов).
(function () {
  const MAX = 15;
  document.querySelectorAll(".searchbox").forEach(function (box) {
    const input = box.querySelector("input[type=search]");
    const list = box.querySelector(".suggest");
    const counter = box.querySelector(".counter");
    let items = [], active = -1, timer = null;

    function words(s) { return (s.toLowerCase().match(/[0-9a-zа-яё]+/gi) || []).length; }

    function updateCounter() {
      if (!counter) return;
      const n = words(input.value);
      counter.textContent = n ? n + " / " + MAX + " сл." : "";
      counter.classList.toggle("over", n > MAX);
    }

    function render() {
      list.innerHTML = "";
      items.forEach(function (text, i) {
        const li = document.createElement("li");
        li.textContent = text;
        if (i === active) li.className = "active";
        li.addEventListener("mousedown", function (e) {
          e.preventDefault();
          input.value = text;
          box.querySelector("form").submit();
        });
        list.appendChild(li);
      });
      list.style.display = items.length ? "block" : "none";
    }

    input.addEventListener("input", function () {
      updateCounter();
      clearTimeout(timer);
      const q = input.value.trim();
      if (!q) { items = []; render(); return; }
      timer = setTimeout(function () {
        fetch("/api/suggest?q=" + encodeURIComponent(q))
          .then(function (r) { return r.json(); })
          .then(function (data) { items = data; active = -1; render(); })
          .catch(function () {});
      }, 120);
    });

    input.addEventListener("keydown", function (e) {
      if (!items.length) return;
      if (e.key === "ArrowDown") { active = (active + 1) % items.length; render(); e.preventDefault(); }
      else if (e.key === "ArrowUp") { active = (active - 1 + items.length) % items.length; render(); e.preventDefault(); }
      else if (e.key === "Enter" && active >= 0) { input.value = items[active]; }
      else if (e.key === "Escape") { items = []; render(); }
    });
    input.addEventListener("blur", function () { setTimeout(function () { list.style.display = "none"; }, 100); });
    updateCounter();
  });
})();
