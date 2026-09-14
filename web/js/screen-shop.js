// screen-shop — 商店 / 背包 / 倉庫
(() => {
  const num = (msg, def) => {
    const raw = prompt(msg, String(def ?? 1));
    if (raw == null) return null;
    const n = Math.floor(Number(raw));
    if (!Number.isFinite(n) || n <= 0) { App.toast("數量不對", true); return null; }
    return n;
  };
  const eqName = (id) => S.catalog?.equipment?.[id]?.name || id;
  const eqSlot = (id) => S.catalog?.equipment?.[id]?.slot || "";

  Screens.shop = {
    async mount() {
      this._tab = "shop";
      this._draw();
    },

    _draw() {
      view().innerHTML = `
        <div class="card">
          <div class="section-title"><h2>商店</h2>
            <span class="pill zeny" style="color:var(--gold)">Zeny ${S.char.zeny}</span></div>
        </div>
        <div id="shop-body"><div class="spinner">載入中…</div></div>`;
      this._drawShop();
    },

    _body() { return document.querySelector("#shop-body"); },
    _stale(tab) { return this._tab !== tab; },   // await 回來時使用者已切走 → 別亂寫

    async _reloadHeader() {
      await App.refreshChar();
      const p = view().querySelector(".pill.zeny");
      if (p) p.textContent = `Zeny ${S.char.zeny}`;
    },

    // ---------- 商店 ----------
    async _drawShop() {
      let data, inv = { items: {} };
      try {
        [data, inv] = await Promise.all([API.shop(), API.inventory(S.char.id).catch(() => ({ items: {} }))]);
      } catch (e) { if (this._stale("shop")) return; this._body().innerHTML = `<div class="card">${esc(e.detail || "載入失敗")}</div>`; return; }
      if (this._stale("shop")) return;
      const owned = inv.items || {};
      const bl = S.char.base_level;
      const cat = this._shopCat || "all";

      // 需求等級標記：不足 → 紅字
      const reqTag = (id, isEq) => {
        const def = isEq ? S.catalog?.equipment?.[id] : S.catalog?.items?.[id];
        const lv = def?.required_level || 1;
        if (lv <= 1) return "";
        const short = bl < lv;
        return `<span style="color:${short ? "var(--bad)" : "var(--muted)"}">需 Lv ${lv}</span>　`;
      };

      const itemRow = (it) => {
        const d = itemDesc(it.id);
        const have = owned[it.id] ? `背包有 ${owned[it.id]}　` : "";
        return `
        <div class="item">
          <div>${esc(it.name)}<div class="sub">${reqTag(it.id, false)}${d ? esc(d) + "　" : ""}${have}賣 ${it.sell_price}</div></div>
          <div class="row tight">
            <button class="btn small primary" data-buy="${it.id}" data-name="${esc(it.name)}">買 ${it.price}</button>
            <button class="btn small" data-sell-item="${it.id}" data-name="${esc(it.name)}">賣</button>
          </div>
        </div>`;
      };
      const wornSlot = (slot) => (inv.equipment || []).find((e) =>
        e.equipped_slot === (slot === "accessory" ? "accessory1" : slot));
      const cmpLine = (eq) => equipCompareLine(wornSlot(eq.slot)?.equipment_id, eq.id);
      const eqRow = (eq) => {
        const d = gearDesc(eq.id);
        return `
        <div class="item" style="align-items:flex-start">
          <div>${esc(eq.name)}<div class="sub">${reqTag(eq.id, true)}${d ? esc(d) + "　" : ""}賣 ${eq.sell_price}</div>
            <div class="sub" style="margin-top:2px">${cmpLine(eq)}</div></div>
          <button class="btn small primary" data-buy="${eq.id}" data-name="${esc(eq.name)}">買 ${eq.price}</button>
        </div>`;
      };

      const SLOTS = [["weapon", "武器"], ["head", "頭部"], ["armor", "鎧甲"],
        ["garment", "披肩"], ["shoes", "鞋子"], ["accessory", "飾品"], ["offhand", "副手"]];
      const opt = (v, zh) => `<option value="${v}"${cat === v ? " selected" : ""}>${zh}</option>`;
      const catSel = `<select id="shop-cat" style="width:100%;margin-bottom:8px">` +
        opt("all", "全部") + opt("item", "道具") + opt("material", "材料") +
        SLOTS.map(([v, zh]) => opt(v, zh)).join("") + `</select>`;

      let sections = "";
      if (cat === "all" || cat === "item") {
        const rows = (data.items || []).filter((it) => it.kind !== "material").map(itemRow).join("");
        sections += `<div class="card"><h3>道具</h3><div class="list">${
          rows || `<p class="muted">沒有商品。</p>`}</div></div>`;
      }
      if (cat === "all" || cat === "material") {
        const rows = (data.items || []).filter((it) => it.kind === "material").map(itemRow).join("");
        sections += `<div class="card"><h3>材料</h3><div class="list">${
          rows || `<p class="muted">沒有商品。</p>`}</div></div>`;
      }
      if (cat !== "item" && cat !== "material") {
        const eqs = (data.equipment || []).filter((e) => cat === "all" || e.slot === cat);
        const rows = eqs.map(eqRow).join("");
        const title = cat === "all" ? "裝備" : (SLOTS.find(([v]) => v === cat)?.[1] || "裝備");
        sections += `<div class="card"><h3>${title}</h3><div class="list">${
          rows || `<p class="muted">沒有商品。</p>`}</div></div>`;
      }

      this._body().innerHTML = `<div class="card">${catSel}</div>${sections}`;
      const cs = this._body().querySelector("#shop-cat");
      if (cs) cs.onchange = () => { this._shopCat = cs.value; this._drawShop(); };

      this._body().querySelectorAll("[data-buy]").forEach((b) => {
        b.onclick = async () => {
          const qty = num(`買幾個「${b.dataset.name}」？`, 1);
          if (qty == null) return;
          b.disabled = true;
          try {
            const r = await API.buy(b.dataset.buy, qty);
            App.toast(`買了 ${b.dataset.name} ×${qty}${r && r.spent != null ? `（-${r.spent}z）` : ""}`);
            await this._reloadHeader();
            if (this._tab === "shop") this._drawShop();
          } catch (e) { App.toast(e.detail || "購買失敗", true); }
          b.disabled = false;
        };
      });
      this._body().querySelectorAll("[data-sell-item]").forEach((b) => {
        b.onclick = async () => {
          const qty = num(`賣幾個「${b.dataset.name}」？`, 1);
          if (qty == null) return;
          b.disabled = true;
          try {
            const r = await API.sell({ item_id: b.dataset.sellItem, qty });
            App.toast(`賣了 ${b.dataset.name} ×${qty}${r && r.gained != null ? `（+${r.gained}z）` : ""}`);
            await this._reloadHeader();
            if (this._tab === "shop") this._drawShop();
          } catch (e) { App.toast(e.detail || "販售失敗", true); }
          b.disabled = false;
        };
      });
    },
  };
})();
