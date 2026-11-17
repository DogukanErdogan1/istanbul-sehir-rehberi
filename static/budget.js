(() => {
  "use strict";
  const I18N = window.GuideI18n || { language: "tr", text: v => v, locale: () => "tr-TR", link: v => v, fold: v => String(v).toLocaleLowerCase("tr-TR"), html: (parts, ...values) => parts.reduce((out, part, index) => out + part + (index < values.length ? values[index] : ""), "") };
  let app;
  let routeId = null;
  let budget = null;
  let generation = 0;
  let editingId = null;
  let deletingId = null;
  let busy = false;
  const $ = selector => document.querySelector(selector);
  const currency = new Intl.NumberFormat(I18N.locale(), { style: "currency", currency: "TRY" });
  const categoryNames = { transport: I18N.text("Ulaşım"), food: I18N.text("Yeme içme"), tickets: I18N.text("Giriş ve bilet"), accommodation: I18N.text("Konaklama"), other: I18N.text("Diğer") };
  const money = kurus => currency.format(kurus / 100);
  const fieldAmount = kurus => Math.floor(kurus / 100) + (I18N.language === "en" ? "." : ",") + String(kurus % 100).padStart(2, "0");
  const h = value => app.escapeHtml(value);

  function amount(value) {
    const normalized = value.trim().replace(",", ".");
    if (!/^(0|[1-9]\d{0,6})(\.\d{1,2})?$/.test(normalized)) {
      throw new Error(I18N.text("Tutarı 1250,50 gibi, binlik ayırıcı kullanmadan ve en fazla iki ondalık basamakla gir."));
    }
    const [whole, fraction = ""] = normalized.split(".");
    const decimals = fraction.padEnd(2, "0");
    return { value: whole + "." + decimals, kurus: Number(whole) * 100 + Number(decimals) };
  }

  function status(message = "", error = false) {
    $("#budgetStatus").textContent = message;
    $("#budgetStatus").dataset.error = String(error);
  }

  function setBusy(value) {
    busy = value;
    $("#budgetContent").setAttribute("aria-busy", String(value));
    document.querySelectorAll("#budgetForm input, #budgetForm select, #budgetForm textarea, #budgetForm button, #budgetItems button").forEach(node => { node.disabled = value; });
    $("#budgetSave").textContent = value ? I18N.text("Kaydediliyor…") : editingId ? I18N.text("Değişiklikleri kaydet") : I18N.text("Kalemi ekle +");
  }

  function resetForm() {
    editingId = null;
    $("#budgetForm").reset();
    $("#budgetFormTitle").textContent = I18N.text("Yeni bir kalem.");
    $("#budgetSave").textContent = I18N.text("Kalemi ekle +");
    $("#budgetCancelEdit").hidden = true;
    $("#budgetFormMessage").textContent = "";
  }

  function render() {
    if (!budget) return;
    const { planned_kurus: planned, spent_kurus: spent, remaining_kurus: remaining, categories } = budget.summary;
    $("#budgetRouteName").textContent = budget.route_title;
    $("#budgetPlanned").textContent = money(planned);
    $("#budgetSpent").textContent = money(spent);
    $("#budgetBalance").textContent = money(Math.abs(remaining));
    $("#budgetBalanceLabel").textContent = remaining < 0 ? I18N.text("PLANIN ÜZERİNDE") : I18N.text("KALAN BÜTÇE");
    $("#budgetSummary").dataset.over = String(remaining < 0);
    const percent = planned ? Math.min(100, spent / planned * 100) : spent ? 100 : 0;
    $("#budgetProgress").value = percent;
    $("#budgetProgressNote").textContent = remaining < 0 ? I18N.text("Planladığın toplamı ") + money(-remaining) + I18N.text(" aştın.") : planned ? I18N.text("Planlanan tutarın %") + Math.round(percent) + I18N.text(" kadarı kullanıldı.") : I18N.text("İlk kalemini ekleyerek gezi bütçeni planlamaya başla.");
    $("#budgetCategories").innerHTML = categories.map(item => `<tr data-over="${item.spent_kurus > item.planned_kurus}"><td>${h(item.label)}</td><td>${h(money(item.planned_kurus))}</td><td>${h(money(item.spent_kurus))}</td></tr>`).join("");
    $("#budgetItemCount").textContent = budget.items.length + I18N.text(" / 200 kalem");
    $("#budgetItems").innerHTML = budget.items.length ? budget.items.map(item => {
      const date = item.spent_on ? new Date(item.spent_on + "T12:00:00").toLocaleDateString(I18N.locale(), { day: "numeric", month: "long", year: "numeric" }) : "";
      const actions = deletingId === item.id
        ? I18N.html`<span class="budget-delete-question">Bu kalem silinsin mi?</span><button type="button" data-budget-confirm="${item.id}">Evet, sil</button><button type="button" data-budget-keep>Vazgeç</button>`
        : I18N.html`<button type="button" data-budget-edit="${item.id}" aria-label="${h(item.title)} kalemini düzenle">Düzenle</button><button type="button" data-budget-delete="${item.id}" aria-label="${h(item.title)} kalemini sil">Sil</button>`;
      return I18N.html`<article class="budget-item"><p class="budget-item-meta"><span>${h(categoryNames[item.category])}</span>${date ? `<time datetime="${h(item.spent_on)}">${h(date)}</time>` : ""}</p><h4>${h(item.title)}</h4>${item.notes ? `<p class="budget-item-notes">${h(item.notes)}</p>` : ""}<div class="budget-item-bottom"><dl class="budget-item-amounts"><div><dt>Planlanan</dt><dd>${h(money(item.planned_kurus))}</dd></div><div><dt>Harcanan</dt><dd>${h(money(item.spent_kurus))}</dd></div></dl><div class="budget-item-actions">${actions}</div></div></article>`;
    }).join("") : I18N.text('<div class="budget-empty">Henüz bir bütçe kalemi yok.<br />Bir yol bileti, bir öğle yemeği ya da ilk kahve molasıyla başla.</div>');
  }

  async function open(id) {
    if (!app.state.user) return app.openAuth("login");
    const route = app.state.routes.find(item => item.id === id);
    if (!route) return;
    const token = ++generation;
    routeId = id;
    budget = null;
    deletingId = null;
    resetForm();
    setBusy(false);
    $("#budgetRouteName").textContent = route.title;
    $("#budgetContent").hidden = true;
    $("#budgetRetry").hidden = true;
    status(I18N.text("Bütçen açılıyor…"));
    if ($("#routeViewDialog").open) $("#routeViewDialog").close();
    if (!$("#budgetDialog").open) $("#budgetDialog").showModal();
    try {
      const result = await app.fetchJson("/api/routes/" + id + "/budget");
      if (token !== generation || !$("#budgetDialog").open) return;
      budget = result;
      render();
      $("#budgetContent").hidden = false;
      status();
    } catch (error) {
      if (token !== generation || !$("#budgetDialog").open) return;
      status(error.message, true);
      $("#budgetRetry").hidden = false;
    }
  }

  function edit(id) {
    const item = budget?.items.find(entry => entry.id === id);
    if (!item || busy) return;
    editingId = id;
    deletingId = null;
    render();
    $("#budgetItemTitle").value = item.title;
    $("#budgetCategory").value = item.category;
    $("#budgetItemPlanned").value = fieldAmount(item.planned_kurus);
    $("#budgetItemSpent").value = fieldAmount(item.spent_kurus);
    $("#budgetDate").value = item.spent_on || "";
    $("#budgetNotes").value = item.notes;
    $("#budgetFormTitle").textContent = I18N.text("Kalemi düzenle.");
    $("#budgetSave").textContent = I18N.text("Değişiklikleri kaydet");
    $("#budgetCancelEdit").hidden = false;
    $("#budgetFormMessage").textContent = "";
    $("#budgetItemTitle").focus();
  }

  async function mutate(method, itemId, payload) {
    if (busy || !budget) return;
    const token = generation;
    setBusy(true);
    $("#budgetFormMessage").textContent = "";
    status();
    try {
      const options = { method };
      if (payload) {
        options.headers = { "Content-Type": "application/json" };
        options.body = JSON.stringify(payload);
      }
      const result = await app.fetchJson("/api/routes/" + routeId + "/budget" + (itemId ? "/" + itemId : ""), options);
      if (token !== generation || !$("#budgetDialog").open) return;
      budget = result;
      deletingId = null;
      if (method !== "DELETE" || editingId === itemId) resetForm();
      render();
      status(method === "DELETE" ? I18N.text("Bütçe kalemi silindi.") : I18N.text("Bütçen kaydedildi."));
    } catch (error) {
      if (token === generation && $("#budgetDialog").open) status(error.message, true);
    } finally {
      if (token === generation) setBusy(false);
    }
  }

  function init(api) {
    app = api;
    $("#budgetDialog").addEventListener("close", () => { generation++; routeId = null; budget = null; });
    $("#budgetRetry").addEventListener("click", () => { if (routeId) open(routeId); });
    $("#budgetCancelEdit").addEventListener("click", resetForm);
    $("#budgetForm").addEventListener("submit", event => {
      event.preventDefault();
      if (busy || !budget) return;
      try {
        const planned = amount($("#budgetItemPlanned").value);
        const spent = amount($("#budgetItemSpent").value);
        const title = $("#budgetItemTitle").value.trim();
        if (title.length < 2) throw new Error(I18N.text("Kalem adı en az iki karakter olmalı."));
        if (!planned.kurus && !spent.kurus) throw new Error(I18N.text("Planlanan veya harcanan tutardan biri sıfırdan büyük olmalı."));
        mutate(editingId ? "PUT" : "POST", editingId, { title, category: $("#budgetCategory").value, planned_amount: planned.value, spent_amount: spent.value, spent_on: $("#budgetDate").value || null, notes: $("#budgetNotes").value.trim() });
      } catch (error) { $("#budgetFormMessage").textContent = error.message; }
    });
    document.addEventListener("click", event => {
      const button = event.target.closest("button");
      if (!button) return;
      if (button.dataset.routeBudget) { open(Number(button.dataset.routeBudget)); return; }
      if (busy || !budget) return;
      if (button.dataset.budgetEdit) edit(Number(button.dataset.budgetEdit));
      if (button.dataset.budgetDelete) { deletingId = Number(button.dataset.budgetDelete); render(); }
      if (button.hasAttribute("data-budget-keep")) { deletingId = null; render(); }
      if (button.dataset.budgetConfirm) mutate("DELETE", Number(button.dataset.budgetConfirm));
    });
  }
  window.GuideBudget = Object.freeze({ init });
})();
