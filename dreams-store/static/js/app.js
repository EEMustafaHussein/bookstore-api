/* ملابس الأحلام — storefront interactions (no dependencies) */
(() => {
  "use strict";

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const finePointer = window.matchMedia("(hover: hover) and (pointer: fine)").matches;
  const csrfToken = () => $('meta[name="csrf-token"]')?.content || "";

  document.documentElement.classList.remove("no-js");

  /* ---------------------------------------------------------- toasts */

  const toastIcons = { success: "check", error: "alert", info: "info" };
  const iconHref = () => {
    const use = $("svg.icon use");
    return use ? use.getAttribute("href").split("#")[0] : "/static/img/icons.svg";
  };

  function makeIcon(name, extraClass = "") {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("class", `icon ${extraClass}`.trim());
    svg.setAttribute("aria-hidden", "true");
    const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
    use.setAttribute("href", `${iconHref()}#${name}`);
    svg.appendChild(use);
    return svg;
  }

  function dismissToast(el) {
    if (!el || el.classList.contains("is-leaving")) return;
    el.classList.add("is-leaving");
    el.addEventListener("animationend", () => el.remove(), { once: true });
    setTimeout(() => el.remove(), 600);
  }

  function armToast(el) {
    const timer = setTimeout(() => dismissToast(el), 5200);
    $("[data-toast-close]", el)?.addEventListener("click", () => {
      clearTimeout(timer);
      dismissToast(el);
    });
  }

  function toast(message, category = "success") {
    const holder = $("[data-toasts]");
    if (!holder || !message) return;
    const el = document.createElement("div");
    el.className = `toast toast-${category}`;
    el.appendChild(makeIcon(toastIcons[category] || "info"));
    const p = document.createElement("p");
    p.textContent = message;
    el.appendChild(p);
    const close = document.createElement("button");
    close.type = "button";
    close.className = "toast-close";
    close.setAttribute("aria-label", "إغلاق");
    close.setAttribute("data-toast-close", "");
    close.appendChild(makeIcon("close"));
    el.appendChild(close);
    holder.appendChild(el);
    while (holder.children.length > 3) holder.firstElementChild.remove();
    armToast(el);
  }
  window.dreamsToast = toast;
  $$("[data-toast]").forEach(armToast);

  /* ---------------------------------------------------------- header & menu */

  const header = $("[data-header]");
  let lastY = window.scrollY;
  let ticking = false;
  function onScroll() {
    const y = window.scrollY;
    if (header) {
      header.classList.toggle("is-scrolled", y > 24);
      const menuOpen = document.body.classList.contains("is-locked");
      header.classList.toggle("is-hidden", !menuOpen && y > 420 && y > lastY + 4);
      if (y < lastY - 4) header.classList.remove("is-hidden");
    }
    lastY = y;
    ticking = false;
  }
  window.addEventListener("scroll", () => {
    if (!ticking) {
      ticking = true;
      requestAnimationFrame(onScroll);
    }
  }, { passive: true });
  onScroll();

  const menu = $("[data-menu]");
  const menuButton = $("[data-menu-open]");
  function setMenu(open) {
    if (!menu) return;
    menu.classList.toggle("is-open", open);
    menu.setAttribute("aria-hidden", String(!open));
    menuButton?.setAttribute("aria-expanded", String(open));
    document.body.classList.toggle("is-locked", open);
    if (open) $("[data-menu-close]", menu)?.focus();
  }
  menuButton?.addEventListener("click", () => setMenu(true));
  $("[data-menu-close]")?.addEventListener("click", () => setMenu(false));
  $$(".mobile-links a").forEach((link) => link.addEventListener("click", () => setMenu(false)));

  /* ---------------------------------------------------------- search overlay */

  const search = $("[data-search]");
  function setSearch(open) {
    if (!search) return;
    search.classList.toggle("is-open", open);
    search.setAttribute("aria-hidden", String(!open));
    document.body.classList.toggle("is-locked", open);
    if (open) setTimeout(() => $("input", search)?.focus(), 80);
  }
  $$("[data-search-open]").forEach((btn) => btn.addEventListener("click", () => setSearch(true)));
  $("[data-search-close]")?.addEventListener("click", () => setSearch(false));
  search?.addEventListener("click", (event) => {
    if (event.target === search) setSearch(false);
  });

  /* ---------------------------------------------------------- split words & reveal */

  $$("[data-split]").forEach((el) => {
    const words = el.textContent.trim().split(/\s+/);
    el.textContent = "";
    words.forEach((word, index) => {
      const outer = document.createElement("span");
      outer.className = "word";
      const inner = document.createElement("span");
      inner.style.setProperty("--w", index);
      inner.textContent = word;
      outer.appendChild(inner);
      el.appendChild(outer);
      if (index < words.length - 1) el.appendChild(document.createTextNode(" "));
    });
    el.classList.add("is-split");
  });

  const revealItems = $$(".reveal");
  if ("IntersectionObserver" in window && !reduceMotion) {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        }
      });
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.08 });
    revealItems.forEach((el) => observer.observe(el));
  } else {
    revealItems.forEach((el) => el.classList.add("is-visible"));
  }

  /* ---------------------------------------------------------- counters */

  function animateCount(el) {
    const target = parseInt(el.dataset.count, 10);
    if (!Number.isFinite(target) || target <= 0 || reduceMotion) return;
    const start = performance.now();
    const duration = 1400;
    const step = (now) => {
      const t = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - t, 3);
      el.textContent = Math.round(target * eased).toLocaleString("en-US");
      if (t < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }
  const counters = $$("[data-count]");
  if ("IntersectionObserver" in window) {
    const countObserver = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          animateCount(entry.target);
          countObserver.unobserve(entry.target);
        }
      });
    });
    counters.forEach((el) => countObserver.observe(el));
  }

  /* ---------------------------------------------------------- starry sky */

  $$("[data-stars]").forEach((canvas) => {
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    let stars = [];
    let shooting = null;
    let running = false;
    let frame = 0;

    function resize() {
      const ratio = Math.min(window.devicePixelRatio || 1, 2);
      const { width, height } = canvas.getBoundingClientRect();
      canvas.width = Math.max(1, width * ratio);
      canvas.height = Math.max(1, height * ratio);
      ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
      const count = Math.min(Math.round((width * height) / 5200), 220);
      stars = Array.from({ length: count }, () => ({
        x: Math.random() * width,
        y: Math.random() * height,
        r: Math.random() * 1.3 + 0.2,
        phase: Math.random() * Math.PI * 2,
        speed: Math.random() * 0.02 + 0.006,
        hue: Math.random() < 0.2 ? "243, 215, 167" : "255, 255, 255",
      }));
      draw();
    }

    function draw() {
      const { width, height } = canvas.getBoundingClientRect();
      ctx.clearRect(0, 0, width, height);
      for (const s of stars) {
        s.phase += reduceMotion ? 0 : s.speed;
        const alpha = 0.35 + Math.sin(s.phase) * 0.35 + 0.3;
        ctx.beginPath();
        ctx.fillStyle = `rgba(${s.hue}, ${alpha.toFixed(3)})`;
        ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
        ctx.fill();
      }
      if (!reduceMotion) {
        if (!shooting && Math.random() < 0.004) {
          shooting = { x: Math.random() * width * 0.8 + width * 0.2, y: Math.random() * height * 0.4, life: 0 };
        }
        if (shooting) {
          shooting.life += 1;
          const len = 90;
          const x = shooting.x - shooting.life * 7;
          const y = shooting.y + shooting.life * 3.2;
          const gradient = ctx.createLinearGradient(x, y, x + len, y - len * 0.45);
          gradient.addColorStop(0, "rgba(255,255,255,0.9)");
          gradient.addColorStop(1, "rgba(255,255,255,0)");
          ctx.strokeStyle = gradient;
          ctx.lineWidth = 1.4;
          ctx.beginPath();
          ctx.moveTo(x, y);
          ctx.lineTo(x + len, y - len * 0.45);
          ctx.stroke();
          if (shooting.life > 60) shooting = null;
        }
      }
    }

    function loop() {
      if (!running) return;
      frame += 1;
      if (frame % 2 === 0) draw();
      requestAnimationFrame(loop);
    }

    resize();
    window.addEventListener("resize", resize);
    if (reduceMotion) return;
    if ("IntersectionObserver" in window) {
      new IntersectionObserver(([entry]) => {
        const visible = entry.isIntersecting;
        if (visible && !running) {
          running = true;
          requestAnimationFrame(loop);
        } else if (!visible) {
          running = false;
        }
      }).observe(canvas);
    } else {
      running = true;
      requestAnimationFrame(loop);
    }
  });

  /* ---------------------------------------------------------- hero parallax, tilt, magnetic */

  const parallax = $("[data-parallax]");
  if (parallax && finePointer && !reduceMotion) {
    const layers = $$("[data-depth]", parallax);
    const hero = parallax.closest("section") || parallax;
    hero.addEventListener("pointermove", (event) => {
      const rect = hero.getBoundingClientRect();
      const dx = (event.clientX - rect.left) / rect.width - 0.5;
      const dy = (event.clientY - rect.top) / rect.height - 0.5;
      layers.forEach((layer) => {
        const depth = parseFloat(layer.dataset.depth) || 1;
        layer.style.transform = `translate3d(${dx * -26 * depth}px, ${dy * -20 * depth}px, 0)`;
      });
    });
    hero.addEventListener("pointerleave", () => layers.forEach((layer) => (layer.style.transform = "")));
  }

  if (finePointer && !reduceMotion) {
    $$("[data-tilt]").forEach((el) => {
      el.addEventListener("pointermove", (event) => {
        const rect = el.getBoundingClientRect();
        const px = (event.clientX - rect.left) / rect.width;
        const py = (event.clientY - rect.top) / rect.height;
        el.style.setProperty("--ry", `${(px - 0.5) * 10}deg`);
        el.style.setProperty("--rx", `${(0.5 - py) * 8}deg`);
        const media = $(".product-media", el);
        media?.style.setProperty("--mx", `${px * 100}%`);
        media?.style.setProperty("--my", `${py * 100}%`);
      });
      el.addEventListener("pointerleave", () => {
        el.style.setProperty("--ry", "0deg");
        el.style.setProperty("--rx", "0deg");
      });
    });

    $$("[data-magnetic]").forEach((el) => {
      el.addEventListener("pointermove", (event) => {
        const rect = el.getBoundingClientRect();
        const x = event.clientX - rect.left - rect.width / 2;
        const y = event.clientY - rect.top - rect.height / 2;
        el.style.transform = `translate(${x * 0.18}px, ${y * 0.28}px)`;
      });
      el.addEventListener("pointerleave", () => (el.style.transform = ""));
    });
  }

  /* ---------------------------------------------------------- forms: steppers, passwords, submit once, confirm */

  $$("[data-stepper]").forEach((stepper) => {
    const input = $("input", stepper);
    if (!input) return;
    $$("[data-step]", stepper).forEach((button) => {
      button.addEventListener("click", () => {
        const min = parseInt(input.min, 10) || 1;
        const max = parseInt(input.max, 10) || 99;
        const next = (parseInt(input.value, 10) || min) + parseInt(button.dataset.step, 10);
        input.value = String(Math.min(Math.max(next, min), max));
      });
    });
  });

  $$("[data-toggle-password]").forEach((button) => {
    button.addEventListener("click", () => {
      const input = button.parentElement.querySelector("input");
      if (!input) return;
      const show = input.type === "password";
      input.type = show ? "text" : "password";
      button.setAttribute("aria-label", show ? "إخفاء كلمة المرور" : "إظهار كلمة المرور");
      $("use", button)?.setAttribute("href", `${iconHref()}#${show ? "eye-off" : "eye"}`);
    });
  });

  $$("[data-strength]").forEach((input) => {
    const meter = input.closest(".field")?.querySelector("[data-strength-meter]");
    if (!meter) return;
    input.addEventListener("input", () => {
      const v = input.value;
      let score = 0;
      if (v.length >= 8) score += 1;
      if (/\d/.test(v) && /\D/.test(v)) score += 1;
      if (/[^\w\s]/.test(v) || /[A-Z]/.test(v)) score += 1;
      if (v.length >= 12) score += 1;
      meter.dataset.level = v ? String(Math.max(score, 1)) : "0";
    });
  });

  function lockSubmit(form, button) {
    if (!button) return;
    setTimeout(() => {
      button.classList.add("is-loading");
      button.disabled = true;
      if (button.dataset.submitLabel) button.textContent = button.dataset.submitLabel;
    }, 0);
  }
  document.addEventListener("submit", (event) => {
    const form = event.target;
    if (event.defaultPrevented || !(form instanceof HTMLFormElement)) return;
    if (form.matches("[data-submit-once-form]")) {
      $$('button[type="submit"]:not([form])', form).forEach((b) => lockSubmit(form, b));
    } else {
      lockSubmit(form, $("[data-submit-once]", form));
    }
  });
  window.addEventListener("pageshow", () => {
    $$("button.is-loading").forEach((b) => {
      b.disabled = false;
      b.classList.remove("is-loading");
    });
  });

  const confirmDialog = $("[data-confirm-dialog]");
  document.addEventListener("submit", (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement) || !form.dataset.confirm) return;
    if (form.dataset.confirmed === "1") {
      delete form.dataset.confirmed;
      return;
    }
    event.preventDefault();
    event.stopImmediatePropagation();
    const submitter = event.submitter || null;
    const proceed = () => {
      form.dataset.confirmed = "1";
      if (submitter && form.requestSubmit) form.requestSubmit(submitter);
      else if (form.requestSubmit) form.requestSubmit();
      else form.submit();
    };
    if (confirmDialog && typeof confirmDialog.showModal === "function") {
      $("[data-confirm-text]", confirmDialog).textContent = form.dataset.confirm;
      confirmDialog.returnValue = "";
      confirmDialog.showModal();
      confirmDialog.addEventListener("close", () => {
        if (confirmDialog.returnValue === "ok") proceed();
      }, { once: true });
    } else if (window.confirm(form.dataset.confirm)) {
      proceed();
    }
  }, true);

  $$("form[data-autosubmit] select").forEach((select) => {
    select.addEventListener("change", () => select.form.submit());
  });

  $$("[data-copy-link]").forEach((button) => {
    button.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(window.location.href);
        toast("تم نسخ رابط القطعة ✨");
      } catch {
        toast("لم نتمكن من نسخ الرابط", "error");
      }
    });
  });

  /* ---------------------------------------------------------- product gallery */

  $$("[data-gallery]").forEach((gallery) => {
    const track = $("[data-gallery-track]", gallery);
    if (!track) return;
    const slides = $$(".gallery-slide", track);
    const thumbs = $$("[data-thumb]", gallery);
    const dots = $$(".gallery-dots span", gallery);
    let current = 0;

    const setActive = (index) => {
      current = index;
      thumbs.forEach((t, i) => t.classList.toggle("is-active", i === index));
      dots.forEach((d, i) => d.classList.toggle("is-active", i === index));
    };
    const goTo = (index) => {
      const target = slides[(index + slides.length) % slides.length];
      if (!target) return;
      // Measured on screen so it works the same in right-to-left pages.
      const offset = target.getBoundingClientRect().left - track.getBoundingClientRect().left;
      track.scrollBy({ left: offset, behavior: reduceMotion ? "auto" : "smooth" });
    };

    if ("IntersectionObserver" in window) {
      const observer = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) setActive(slides.indexOf(entry.target));
        });
      }, { root: track, threshold: 0.6 });
      slides.forEach((slide) => observer.observe(slide));
    }
    thumbs.forEach((thumb) => thumb.addEventListener("click", () => goTo(parseInt(thumb.dataset.thumb, 10))));
    $("[data-gallery-prev]", gallery)?.addEventListener("click", () => goTo(current - 1));
    $("[data-gallery-next]", gallery)?.addEventListener("click", () => goTo(current + 1));

    if (finePointer) {
      $$("[data-zoom]", gallery).forEach((slide) => {
        slide.addEventListener("pointerenter", () => slide.classList.add("is-zoomed"));
        slide.addEventListener("pointerleave", () => slide.classList.remove("is-zoomed"));
        slide.addEventListener("pointermove", (event) => {
          const rect = slide.getBoundingClientRect();
          slide.style.setProperty("--zx", `${((event.clientX - rect.left) / rect.width) * 100}%`);
          slide.style.setProperty("--zy", `${((event.clientY - rect.top) / rect.height) * 100}%`);
        });
      });
    }
  });

  /* ---------------------------------------------------------- cart drawer */

  const drawer = $("[data-cart-drawer]");
  const backdrop = $("[data-drawer-backdrop]");
  const countBadges = $$("[data-cart-count]");
  const onCartPage = ["/cart", "/checkout"].includes(window.location.pathname);

  function setCount(count) {
    countBadges.forEach((badge) => {
      badge.textContent = String(count);
      badge.hidden = !count;
      badge.classList.remove("is-bumped");
      void badge.offsetWidth;
      badge.classList.add("is-bumped");
    });
  }

  async function cartRequest(url, body) {
    const response = await fetch(url, {
      method: body ? "POST" : "GET",
      body,
      headers: { Accept: "application/json", "X-CSRF-Token": csrfToken() },
      credentials: "same-origin",
    });
    let data = {};
    try {
      data = await response.json();
    } catch {
      data = {};
    }
    if (!response.ok && !data.message) data.message = "حدث خطأ، حدّثي الصفحة وحاولي مجدداً";
    data.ok = response.ok && data.ok !== false;
    return data;
  }

  function renderCart(cart) {
    if (!drawer || !cart) return;
    const body = $("[data-drawer-body]", drawer);
    const foot = $("[data-drawer-foot]", drawer);
    const shipping = $("[data-drawer-shipping]", drawer);
    body.textContent = "";
    setCount(cart.count || 0);

    if (!cart.items || !cart.items.length) {
      const template = $("[data-drawer-empty]", drawer);
      body.appendChild(template.content.cloneNode(true));
      foot.hidden = true;
      shipping.hidden = true;
      return;
    }

    cart.items.forEach((item, index) => {
      const row = document.createElement("div");
      row.className = "drawer-item";
      row.style.setProperty("--i", index);

      const imgLink = document.createElement("a");
      imgLink.href = item.url;
      const img = document.createElement("img");
      img.src = item.image;
      img.alt = item.name;
      img.loading = "lazy";
      imgLink.appendChild(img);

      const info = document.createElement("div");
      const name = document.createElement("a");
      name.href = item.url;
      name.className = "drawer-item-name";
      name.textContent = item.name;
      const meta = document.createElement("p");
      meta.className = "drawer-item-meta";
      meta.textContent = [item.size && `المقاس: ${item.size}`, item.color && `اللون: ${item.color}`, item.unit_text]
        .filter(Boolean)
        .join(" · ");
      const stepper = document.createElement("div");
      stepper.className = "stepper";
      const plus = document.createElement("button");
      plus.type = "button";
      plus.setAttribute("aria-label", "زيادة");
      plus.disabled = item.quantity >= item.max;
      plus.appendChild(makeIcon("plus"));
      plus.addEventListener("click", () => updateItem(row, item.id, item.quantity + 1));
      const value = document.createElement("span");
      value.className = "stepper-value";
      value.textContent = item.quantity;
      const minus = document.createElement("button");
      minus.type = "button";
      minus.setAttribute("aria-label", "إنقاص");
      minus.appendChild(makeIcon("minus"));
      minus.addEventListener("click", () => updateItem(row, item.id, item.quantity - 1));
      stepper.append(plus, value, minus);
      info.append(name, meta, stepper);

      const side = document.createElement("div");
      side.className = "drawer-item-side";
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "icon-btn";
      remove.setAttribute("aria-label", `إزالة ${item.name}`);
      remove.appendChild(makeIcon("trash"));
      remove.addEventListener("click", () => removeItem(row, item.id));
      const total = document.createElement("strong");
      total.textContent = item.line_text;
      side.append(remove, total);

      row.append(imgLink, info, side);
      body.appendChild(row);
    });

    $("[data-drawer-subtotal]", drawer).textContent = cart.subtotal_text;
    $("[data-drawer-shippingfee]", drawer).textContent = cart.shipping_text;
    $("[data-drawer-total]", drawer).textContent = cart.total_text;
    foot.hidden = false;

    if (cart.free_shipping_over) {
      shipping.hidden = false;
      $("[data-drawer-shipping-text]", drawer).textContent = cart.remaining_for_free
        ? `أضيفي ${cart.remaining_text} لتحصلي على توصيل مجاني ✨`
        : "مبروك! حصلتِ على توصيل مجاني 🎉";
      $("[data-drawer-progress]", drawer).style.width = `${cart.progress}%`;
    } else {
      shipping.hidden = true;
    }
    (cart.notices || []).forEach((notice) => toast(notice, "info"));
  }

  async function refreshCart() {
    try {
      renderCart(await cartRequest("/api/cart"));
    } catch {
      toast("تعذّر تحميل السلة، تحققي من الاتصال", "error");
    }
  }

  async function updateItem(row, id, quantity) {
    row.classList.add("is-busy");
    const body = new FormData();
    body.append("quantity", String(quantity));
    try {
      const data = await cartRequest(`/cart/items/${id}`, body);
      if (!data.ok) toast(data.message, "error");
      renderCart(data.cart);
    } catch {
      row.classList.remove("is-busy");
      toast("تعذّر تحديث السلة، تحققي من الاتصال", "error");
    }
  }

  async function removeItem(row, id) {
    row.classList.add("is-busy");
    try {
      const data = await cartRequest(`/cart/items/${id}/remove`, new FormData());
      if (!data.ok) toast(data.message, "error");
      renderCart(data.cart);
    } catch {
      row.classList.remove("is-busy");
      toast("تعذّر تحديث السلة، تحققي من الاتصال", "error");
    }
  }

  let lastFocus = null;
  function openDrawer() {
    if (!drawer) return;
    lastFocus = document.activeElement;
    backdrop.hidden = false;
    requestAnimationFrame(() => backdrop.classList.add("is-open"));
    drawer.classList.add("is-open");
    drawer.setAttribute("aria-hidden", "false");
    document.body.classList.add("is-locked");
    drawer.focus({ preventScroll: true });
    refreshCart();
  }
  function closeDrawer() {
    if (!drawer || !drawer.classList.contains("is-open")) return;
    drawer.classList.remove("is-open");
    drawer.setAttribute("aria-hidden", "true");
    backdrop.classList.remove("is-open");
    document.body.classList.remove("is-locked");
    setTimeout(() => (backdrop.hidden = true), 400);
    lastFocus?.focus?.({ preventScroll: true });
  }
  $$("[data-cart-open]").forEach((link) => {
    link.addEventListener("click", (event) => {
      if (onCartPage || !drawer) return;
      event.preventDefault();
      openDrawer();
    });
  });
  $("[data-drawer-close]")?.addEventListener("click", closeDrawer);
  backdrop?.addEventListener("click", closeDrawer);

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    closeDrawer();
    setMenu(false);
    setSearch(false);
  });

  function flyToCart(sourceImg) {
    const target = $(".cart-btn");
    if (!sourceImg || !target || reduceMotion) return Promise.resolve();
    const from = sourceImg.getBoundingClientRect();
    const to = target.getBoundingClientRect();
    if (!from.width || !to.width) return Promise.resolve();
    const dot = document.createElement("img");
    dot.src = sourceImg.currentSrc || sourceImg.src;
    dot.className = "fly-dot";
    dot.alt = "";
    document.body.appendChild(dot);
    const startX = from.left + from.width / 2 - 32;
    const startY = from.top + from.height / 2 - 32;
    const endX = to.left + to.width / 2 - 32;
    const endY = to.top + to.height / 2 - 32;
    const animation = dot.animate(
      [
        { transform: `translate(${startX}px, ${startY}px) scale(1.6)`, opacity: 0.95 },
        { transform: `translate(${(startX + endX) / 2}px, ${Math.min(startY, endY) - 120}px) scale(1)`, opacity: 1, offset: 0.55 },
        { transform: `translate(${endX}px, ${endY}px) scale(0.2)`, opacity: 0.3 },
      ],
      { duration: 850, easing: "cubic-bezier(.5,0,.3,1)" }
    );
    return animation.finished.then(() => dot.remove()).catch(() => dot.remove());
  }

  $$("form[data-add-to-cart]").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const missing = $$(".option-group", form).filter((group) => !$("input:checked", group));
      $$(".option-group", form).forEach((group) => group.classList.toggle("is-missing", missing.includes(group)));
      if (missing.length) {
        toast(`اختاري ${missing.map((g) => (g.dataset.option === "size" ? "المقاس" : "اللون")).join(" و")} أولاً`, "info");
        return;
      }
      const button = event.submitter || $('button[type="submit"]', form);
      button?.classList.add("is-loading");
      try {
        const data = await cartRequest(form.action, new FormData(form));
        if (!data.ok) {
          toast(data.message, "error");
          return;
        }
        const card = form.closest(".product-card");
        const image = card ? $(".img-main", card) : $(".gallery-slide img");
        await flyToCart(image);
        setCount(data.cart.count);
        $(".cart-btn")?.classList.add("is-wiggling");
        setTimeout(() => $(".cart-btn")?.classList.remove("is-wiggling"), 800);
        if (card) {
          button?.classList.add("is-added");
          setTimeout(() => button?.classList.remove("is-added"), 1600);
          toast(data.message);
        } else {
          renderCart(data.cart);
          openDrawer();
        }
      } catch {
        toast("تعذّر الاتصال، تحققي من الإنترنت وحاولي مجدداً", "error");
      } finally {
        button?.classList.remove("is-loading");
        if (button) button.disabled = false;
      }
    });
  });

  $$(".option-group input").forEach((input) => {
    input.addEventListener("change", () => input.closest(".option-group")?.classList.remove("is-missing"));
  });

  /* ---------------------------------------------------------- order celebration */

  if ($("[data-celebrate]") && !reduceMotion) {
    const canvas = document.createElement("canvas");
    canvas.className = "confetti";
    document.body.appendChild(canvas);
    const ctx = canvas.getContext("2d");
    const ratio = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = window.innerWidth * ratio;
    canvas.height = window.innerHeight * ratio;
    ctx.scale(ratio, ratio);
    const colors = ["#f3b2c3", "#c9a3ec", "#ecc995", "#6b2f80", "#ffffff", "#23936a"];
    const pieces = Array.from({ length: 160 }, () => ({
      x: window.innerWidth / 2 + (Math.random() - 0.5) * 120,
      y: window.innerHeight * 0.35,
      vx: (Math.random() - 0.5) * 16,
      vy: Math.random() * -14 - 4,
      size: Math.random() * 7 + 4,
      rot: Math.random() * Math.PI,
      vr: (Math.random() - 0.5) * 0.3,
      color: colors[Math.floor(Math.random() * colors.length)],
    }));
    const started = performance.now();
    const tick = (now) => {
      ctx.clearRect(0, 0, window.innerWidth, window.innerHeight);
      pieces.forEach((p) => {
        p.vy += 0.35;
        p.vx *= 0.99;
        p.x += p.vx;
        p.y += p.vy;
        p.rot += p.vr;
        ctx.save();
        ctx.translate(p.x, p.y);
        ctx.rotate(p.rot);
        ctx.fillStyle = p.color;
        ctx.fillRect(-p.size / 2, -p.size / 4, p.size, p.size / 2);
        ctx.restore();
      });
      if (now - started < 3500) requestAnimationFrame(tick);
      else canvas.remove();
    };
    requestAnimationFrame(tick);
  }
})();
