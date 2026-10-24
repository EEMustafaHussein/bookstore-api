/* Dashboard helpers: sidebar, image uploads, tag suggestions, counters */
(() => {
  "use strict";

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

  const sidebar = $("[data-admin-sidebar]");
  const backdrop = $("[data-admin-backdrop]");
  const setSidebar = (open) => {
    sidebar?.classList.toggle("is-open", open);
    backdrop?.classList.toggle("is-open", open);
  };
  $("[data-admin-menu]")?.addEventListener("click", () => setSidebar(true));
  backdrop?.addEventListener("click", () => setSidebar(false));
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") setSidebar(false);
  });

  /* image dropzone with previews */
  $$("[data-dropzone]").forEach((zone) => {
    const input = $("[data-dropzone-input]", zone);
    const list = zone.parentElement.querySelector("[data-dropzone-previews]");
    if (!input || !list) return;
    let files = [];
    const canEditList = typeof DataTransfer === "function";

    const sync = () => {
      if (canEditList) {
        const transfer = new DataTransfer();
        files.forEach((file) => transfer.items.add(file));
        input.files = transfer.files;
      }
      list.textContent = "";
      files.forEach((file, index) => {
        const item = document.createElement("li");
        const img = document.createElement("img");
        img.alt = file.name;
        const url = URL.createObjectURL(file);
        img.src = url;
        img.addEventListener("load", () => URL.revokeObjectURL(url), { once: true });
        const label = document.createElement("span");
        label.textContent = `${(file.size / 1024 / 1024).toFixed(1)} MB`;
        item.append(img, label);
        if (canEditList) {
          const remove = document.createElement("button");
          remove.type = "button";
          remove.className = "preview-remove";
          remove.setAttribute("aria-label", "إزالة الصورة");
          remove.textContent = "×";
          remove.addEventListener("click", () => {
            files.splice(index, 1);
            sync();
          });
          item.appendChild(remove);
        }
        list.appendChild(item);
      });
      zone.classList.toggle("has-files", files.length > 0);
    };

    const addFiles = (incoming) => {
      const images = Array.from(incoming).filter((file) => file.type.startsWith("image/") || /\.avif$/i.test(file.name));
      files = canEditList ? files.concat(images) : images;
      sync();
    };

    input.addEventListener("change", () => addFiles(input.files));
    ["dragenter", "dragover"].forEach((type) =>
      zone.addEventListener(type, (event) => {
        event.preventDefault();
        zone.classList.add("is-dragging");
      })
    );
    ["dragleave", "drop"].forEach((type) =>
      zone.addEventListener(type, (event) => {
        event.preventDefault();
        zone.classList.remove("is-dragging");
      })
    );
    zone.addEventListener("drop", (event) => {
      if (event.dataTransfer?.files?.length) addFiles(event.dataTransfer.files);
    });
  });

  /* quick tags for sizes and colours */
  $$("[data-tag-target]").forEach((box) => {
    const input = document.getElementById(box.dataset.tagTarget);
    if (!input) return;
    const current = () => input.value.split(/[,،]/).map((v) => v.trim()).filter(Boolean);
    const paint = () => {
      const values = current();
      $$("[data-tag]", box).forEach((button) => button.classList.toggle("is-on", values.includes(button.dataset.tag)));
    };
    $$("[data-tag]", box).forEach((button) => {
      button.addEventListener("click", () => {
        const values = current();
        const tag = button.dataset.tag;
        const next = values.includes(tag) ? values.filter((v) => v !== tag) : values.concat(tag);
        input.value = next.join(", ");
        paint();
      });
    });
    input.addEventListener("input", paint);
    paint();
  });

  /* character counters */
  $$("[data-counter]").forEach((field) => {
    const output = field.closest(".field")?.querySelector("[data-counter-value]");
    if (!output) return;
    const update = () => (output.textContent = String(field.value.length));
    field.addEventListener("input", update);
    update();
  });

  /* live preview of the about photo */
  const photoInput = $("[data-photo-input]");
  const photoPreview = $("[data-photo-preview]");
  photoInput?.addEventListener("change", () => {
    const file = photoInput.files?.[0];
    if (!file || !photoPreview) return;
    const img = document.createElement("img");
    img.alt = "";
    img.src = URL.createObjectURL(file);
    photoPreview.textContent = "";
    photoPreview.appendChild(img);
  });
})();
