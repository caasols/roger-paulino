// Minimal, dependency-free behavior: mobile nav toggle + gallery lightbox.
(function () {
  "use strict";

  // Mobile nav
  var toggle = document.querySelector(".nav-toggle");
  var nav = document.querySelector(".site-nav");
  if (toggle && nav) {
    toggle.addEventListener("click", function () {
      var open = nav.classList.toggle("is-open");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }

  // Lightbox with prev/next navigation across the page's gallery images
  var IMG_HREF = /\.(jpe?g|png|webp|gif)$/i;
  var links = [];       // the set of gallery links being browsed
  var index = -1;       // current position in `links`

  var box = document.createElement("div");
  box.className = "lightbox";
  box.setAttribute("role", "dialog");
  box.setAttribute("aria-modal", "true");
  box.setAttribute("aria-label", "Image viewer");
  box.innerHTML =
    '<button class="lightbox__nav lightbox__prev" type="button" aria-label="Previous image">&#8249;</button>' +
    '<img alt="">' +
    '<button class="lightbox__nav lightbox__next" type="button" aria-label="Next image">&#8250;</button>' +
    '<button class="lightbox__close" type="button" aria-label="Close">&times;</button>';
  document.body.appendChild(box);
  var boxImg = box.querySelector("img");
  var closeBtn = box.querySelector(".lightbox__close");
  var prevBtn = box.querySelector(".lightbox__prev");
  var nextBtn = box.querySelector(".lightbox__next");
  var lastFocused = null;

  function galleryImageLinks() {
    return Array.prototype.filter.call(
      document.querySelectorAll("a.gallery__item"),
      function (a) { return IMG_HREF.test(a.getAttribute("href") || ""); }
    );
  }

  function showAt(i) {
    if (!links.length) return;
    index = (i + links.length) % links.length;   // wrap around
    var link = links[index];
    var img = link.querySelector("img");
    boxImg.src = link.getAttribute("href");
    boxImg.alt = img ? img.alt : "";
    var multi = links.length > 1;
    prevBtn.hidden = !multi;
    nextBtn.hidden = !multi;
  }

  function open(link) {
    links = galleryImageLinks();
    lastFocused = document.activeElement;
    showAt(links.indexOf(link));
    box.classList.add("is-open");
    document.body.style.overflow = "hidden";
    closeBtn.focus();
  }
  function close() {
    box.classList.remove("is-open");
    boxImg.src = "";
    document.body.style.overflow = "";
    if (lastFocused && lastFocused.focus) lastFocused.focus();
    lastFocused = null;
  }
  function isOpen() { return box.classList.contains("is-open"); }

  document.addEventListener("click", function (e) {
    var link = e.target.closest ? e.target.closest("a.gallery__item") : null;
    if (!link) return;
    if (IMG_HREF.test(link.getAttribute("href") || "")) {
      e.preventDefault();
      open(link);
    }
  });

  // background click closes; image/controls do not
  box.addEventListener("click", close);
  boxImg.addEventListener("click", function (e) { e.stopPropagation(); close(); });
  closeBtn.addEventListener("click", function (e) { e.stopPropagation(); close(); });
  prevBtn.addEventListener("click", function (e) { e.stopPropagation(); showAt(index - 1); });
  nextBtn.addEventListener("click", function (e) { e.stopPropagation(); showAt(index + 1); });

  document.addEventListener("keydown", function (e) {
    if (!isOpen()) return;
    if (e.key === "Escape") {
      close();
    } else if (e.key === "ArrowRight") {
      e.preventDefault(); showAt(index + 1);
    } else if (e.key === "ArrowLeft") {
      e.preventDefault(); showAt(index - 1);
    } else if (e.key === "Tab") {
      e.preventDefault();  // trap focus among the visible controls
      var controls = [prevBtn, nextBtn, closeBtn].filter(function (b) { return !b.hidden; });
      var at = controls.indexOf(document.activeElement);
      var dir = e.shiftKey ? -1 : 1;
      controls[(at + dir + controls.length) % controls.length].focus();
    }
  });

  // Footer copyright year: always the current year (the built-in value is the no-JS fallback)
  Array.prototype.forEach.call(document.querySelectorAll(".js-year"), function (el) {
    el.textContent = new Date().getFullYear();
  });
})();
