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

  // Lightbox for any link that points straight at an image
  var box = document.createElement("div");
  box.className = "lightbox";
  box.innerHTML =
    '<button class="lightbox__close" aria-label="Close">&times;</button><img alt="">';
  document.body.appendChild(box);
  var boxImg = box.querySelector("img");

  function open(src, alt) {
    boxImg.src = src;
    boxImg.alt = alt || "";
    box.classList.add("is-open");
    document.body.style.overflow = "hidden";
  }
  function close() {
    box.classList.remove("is-open");
    boxImg.src = "";
    document.body.style.overflow = "";
  }

  document.addEventListener("click", function (e) {
    var link = e.target.closest ? e.target.closest("a.gallery__item") : null;
    if (!link) return;
    var href = link.getAttribute("href") || "";
    if (/\.(jpe?g|png|webp|gif)$/i.test(href)) {
      e.preventDefault();
      var img = link.querySelector("img");
      open(href, img ? img.alt : "");
    }
  });

  box.addEventListener("click", close);
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && box.classList.contains("is-open")) close();
  });
})();
