// screen-bag — 背包 / 倉庫
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

  Screens.bag = {
    async mount() {
      this._tab = this._tab || "bag";
      this._draw();
    },

    _draw() {
      const tab = this._tab;
      view().innerHTML = `
        <div class="card">
          <div class="section-title"><h2>${tab === "storage" ? "倉庫" : "背包"}</h2>
            <span class="pill zeny" style="color:var(--gold)">Zeny ${S.char.zeny}</span></div>
          <div class="row tight">
            <button class="btn small ${tab === "bag" ? "primary" : ""}" data-tab="bag">背包</button>
            <button class="btn small ${tab === "storage" ? "primary" : ""}" data-tab="storage">倉庫</button>
          </div>
        </div>
        <div id="bag-body"><div class="spinner">載入中…</div></div>`;
      view().querySelectorAll("[data-tab]").forEach((b) => {
        b.onclick = () => { this._tab = b.dataset.tab; this._draw(); };
      });
      if (tab === "storage") this._drawStorage();
      else this._drawBag();
    },

    _body() { return document.querySelector("#bag-body"); },
    _stale(tab) { return this._tab !== tab; },   // await 回來時使用者已切走 → 別亂寫

    async _reloadHeader() {
      await App.refreshChar();
      const p = view().querySelector(".pill.zeny");
      if (p) p.textContent = `Zeny ${S.char.zeny}`;
    },

    // ---------- 背包 / 裝備 ----------
    async _drawBag() {
      let inv;
      try { inv = await API.inventory(S.char.id); }
      catch (e) { if (this._stale("bag")) return; this._body().innerHTML = `<div class="card">${esc(e.detail || "載入失敗")}</div>`; return; }
      if (this._stale("bag")) return;

      const items = inv.items || {};
      const isCard = (id) => !!S.catalog?.cards?.[id];

      // 每張已鑲嵌的卡片鑲在哪些裝備上
      const socketedIn = {};
      for (const inst of inv.equipment || []) {
        for (const cid of inst.card_ids || []) {
          const tag = `${eqName(inst.equipment_id)}${inst.refine ? ` +${inst.refine}` : ""}`;
          (socketedIn[cid] = socketedIn[cid] || []).push(tag);
        }
      }

      const itemRows = Object.entries(items).filter(([id]) => !isCard(id)).map(([id, qty]) => {
        const d = itemDesc(id);
        return `
        <div class="item">
          <div>${esc(itemName(id))}<div class="sub">×${qty}${d ? "　" + esc(d) : ""}</div></div>
          <button class="btn small" data-sell="${id}" data-name="${esc(itemName(id))}">賣</button>
        </div>`; }).join("");

      // 卡片：背包持有的 + 已鑲在裝備上的，都列出來
      const cardIds = [...new Set([
        ...Object.keys(items).filter(isCard),
        ...Object.keys(socketedIn),
      ])];
      const cardRows = cardIds.map((id) => {
        const held = items[id] || 0;
        const where = socketedIn[id] || [];
        const status = where.length
          ? `<span class="pill good">已鑲：${esc(where.join("、"))}</span>`
          : (held ? `<span class="pill">未鑲嵌</span>` : "");
        return `
        <div class="item" style="align-items:flex-start">
          <div>${esc(itemName(id))}
            <div class="sub">${esc(cardDesc(id))}　持有 ${held}</div>
            <div style="margin-top:4px">${status}</div>
          </div>
        </div>`; }).join("");

      const baseSlot = (s) => (s === "accessory1" || s === "accessory2" ? "accessory" : s);
      const slotOf = (eqId) => S.catalog?.equipment?.[eqId]?.slot || "";

      // 目前每個部位穿著什麼（給沒穿的同部位裝備當比較基準）
      const wornBySlot = {};
      for (const inst of inv.equipment || []) {
        if (inst.equipped_slot == null) continue;
        const tag = `${eqName(inst.equipment_id)}${inst.refine ? ` +${inst.refine}` : ""}`;
        (wornBySlot[baseSlot(inst.equipped_slot)] = wornBySlot[baseSlot(inst.equipped_slot)] || []).push(tag);
      }

      // 部位篩選下拉：只列出背包裡實際有的部位
      const slotsPresent = [...new Set((inv.equipment || []).map((i) => slotOf(i.equipment_id)).filter(Boolean))];
      if (this._bagSlot && !slotsPresent.includes(this._bagSlot)) this._bagSlot = "";
      const slotOptions = [`<option value="">全部部位</option>`].concat(
        slotsPresent.map((s) => `<option value="${s}"${this._bagSlot === s ? " selected" : ""}>${SLOT_ZH[s] || s}</option>`),
      ).join("");

      const eqRows = (inv.equipment || [])
        .filter((inst) => !this._bagSlot || slotOf(inst.equipment_id) === this._bagSlot)
        .map((inst) => {
          const equipped = inst.equipped_slot != null;
          const cards = (inst.card_ids || []).map((c) => itemName(c)).join("、");
          const slotZh = equipped ? `　裝備中（${SLOT_ZH[inst.equipped_slot] || inst.equipped_slot}）` : "";
          const worn = !equipped ? (wornBySlot[slotOf(inst.equipment_id)] || []) : [];
          const wornLine = worn.length
            ? `<div class="sub" style="color:var(--muted)">目前穿：${esc(worn.join("、"))}</div>`
            : (!equipped && slotOf(inst.equipment_id)
              ? `<div class="sub" style="color:var(--muted)">目前這個部位沒穿東西</div>` : "");
          const def = S.catalog?.equipment?.[inst.equipment_id];
          const canRefine = def && def.refinable !== false && (inst.refine || 0) < 10;
          const oreName = slotOf(inst.equipment_id) === "weapon" ? "神之金屬" : "鋁";
          const refCost = ((inst.refine || 0) + 1) * 200;
          const refLine = canRefine
            ? `<div class="sub" style="color:var(--muted)">精煉需：${oreName} ×1、Zeny ${refCost}（材料靠打怪掉）</div>`
            : "";
          return `
        <div class="item" style="align-items:flex-start">
          <div>${esc(eqName(inst.equipment_id))}${inst.refine ? ` <span class="pill good">+${inst.refine}</span>` : ""}
            <div class="sub">${esc(gearDesc(inst.equipment_id) || "")}${slotZh}${cards ? `　卡：${esc(cards)}` : ""}</div>
            ${wornLine}
            ${refLine}
            <div class="row tight" style="margin-top:6px">
              ${equipped
                ? `<button class="btn small" data-unequip="${inst.equipped_slot}">卸下</button>`
                : `<button class="btn small primary" data-equip="${inst.id}">裝備</button>`}
              ${canRefine ? `<button class="btn small" data-refine="${inst.id}">精煉</button>` : ""}
              <button class="btn small" data-socket="${inst.id}">鑲卡</button>
              ${equipped ? "" : `<button class="btn small" data-sell-eq="${inst.id}" data-name="${esc(eqName(inst.equipment_id))}">賣出</button>`}
            </div>
          </div>
        </div>`;
        }).join("");

      this._body().innerHTML = `
        <div class="card"><h3>道具</h3>
          <div class="list">${itemRows || `<p class="muted">背包沒有道具。</p>`}</div></div>
        ${cardRows ? `<div class="card"><h3>卡片</h3><div class="list">${cardRows}</div></div>` : ""}
        <div class="card"><h3>裝備</h3>
          <div class="row" style="margin-bottom:8px">
            <select id="bag-slot" style="flex:1">${slotOptions}</select>
          </div>
          <div class="list">${eqRows || `<p class="muted">${this._bagSlot ? "這個部位沒有裝備。" : "背包沒有裝備。"}</p>`}</div></div>`;

      const slotSel = this._body().querySelector("#bag-slot");
      if (slotSel) slotSel.onchange = () => { this._bagSlot = slotSel.value; this._drawBag(); };

      const reload = () => this._drawBag();

      this._body().querySelectorAll("[data-sell]").forEach((b) => {
        b.onclick = async () => {
          const qty = num(`賣幾個「${b.dataset.name}」？`, 1);
          if (qty == null) return;
          b.disabled = true;
          try {
            const r = await API.sell({ item_id: b.dataset.sell, qty });
            App.toast(`賣了 ${b.dataset.name} ×${qty}${r && r.gained != null ? `（+${r.gained}z）` : ""}`);
            await this._reloadHeader();
            reload();
          } catch (e) { App.toast(e.detail || "販售失敗", true); b.disabled = false; }
        };
      });
      this._body().querySelectorAll("[data-sell-eq]").forEach((b) => {
        b.onclick = async () => {
          if (!confirm(`確定賣出「${b.dataset.name}」？賣掉就拿不回來了。`)) return;
          b.disabled = true;
          try {
            const r = await API.sell({ equipment_instance_id: Number(b.dataset.sellEq) });
            App.toast(`賣了 ${b.dataset.name}${r && r.gained != null ? `（+${r.gained}z）` : ""}`);
            await this._reloadHeader();
            reload();
          } catch (e) { App.toast(e.detail || "販售失敗", true); b.disabled = false; }
        };
      });
      this._body().querySelectorAll("[data-equip]").forEach((b) => {
        b.onclick = async () => {
          b.disabled = true;
          try { await API.equip(S.char.id, b.dataset.equip); App.toast("已裝備"); await App.refreshChar(); reload(); }
          catch (e) { App.toast(e.detail || "裝備失敗", true); b.disabled = false; }
        };
      });
      this._body().querySelectorAll("[data-unequip]").forEach((b) => {
        b.onclick = async () => {
          b.disabled = true;
          try { await API.unequip(S.char.id, b.dataset.unequip); App.toast("已卸下"); await App.refreshChar(); reload(); }
          catch (e) { App.toast(e.detail || "卸下失敗", true); b.disabled = false; }
        };
      });
      this._body().querySelectorAll("[data-refine]").forEach((b) => {
        b.onclick = async () => {
          const choice = prompt(
            "選擇精煉模式：\n1. 普通（成功率／失敗降級）\n2. 隨機（+0／+1／+2／+3）",
            "1",
          );
          if (choice == null) return;
          const mode = choice.trim() === "2" ? "random" :
            (choice.trim() === "1" ? "normal" : null);
          if (!mode) { App.toast("模式不對", true); return; }
          b.disabled = true;
          try {
            const r = await API.refine(S.char.id, b.dataset.refine, mode);
            App.toast(r.message || (r.success ? `精煉成功 +${r.refine}` : "精煉失敗"), !r.success);
            await this._reloadHeader();
            reload();
          } catch (e) { App.toast(e.detail || "精煉失敗", true); b.disabled = false; }
        };
      });
      this._body().querySelectorAll("[data-socket]").forEach((b) => {
        b.onclick = async () => {
          const cardId = this._pickCard(inv.items || {});
          if (!cardId) return;
          b.disabled = true;
          try {
            await API.socket(S.char.id, b.dataset.socket, cardId);
            App.toast("鑲卡成功");
            await App.refreshChar();
            reload();
          } catch (e) { App.toast(e.detail || "鑲卡失敗", true); b.disabled = false; }
        };
      });
    },

    _pickCard(items) {
      const cards = Object.keys(items).filter((id) => S.catalog?.cards?.[id]);
      if (!cards.length) { App.toast("背包沒有卡片", true); return null; }
      const list = cards.map((id, i) => `${i + 1}. ${itemName(id)} ×${items[id]}`).join("\n");
      const pick = prompt(`要鑲哪張卡？輸入編號：\n${list}`, "1");
      if (pick == null) return null;
      const idx = Math.floor(Number(pick)) - 1;
      if (idx < 0 || idx >= cards.length) { App.toast("編號不對", true); return null; }
      return cards[idx];
    },

    // ---------- 倉庫 ----------
    async _drawStorage() {
      let st;
      try { st = await API.storage(); }
      catch (e) { if (this._stale("storage")) return; this._body().innerHTML = `<div class="card">${esc(e.detail || "載入失敗")}</div>`; return; }
      if (this._stale("storage")) return;

      const items = st.items || {};
      const itemRows = Object.entries(items).map(([id, qty]) => `
        <div class="item">
          <div>${esc(itemName(id))}<div class="sub">×${qty}</div></div>
          <button class="btn small" data-withdraw-item="${id}" data-name="${esc(itemName(id))}">取出</button>
        </div>`).join("");

      const eqRows = (st.equipment || []).map((inst) => `
        <div class="item">
          <div>${esc(eqName(inst.equipment_id))}${inst.refine ? ` <span class="pill good">+${inst.refine}</span>` : ""}
            <div class="sub">${esc(eqSlot(inst.equipment_id) || "")}</div></div>
          <button class="btn small" data-withdraw-eq="${inst.id}">取出</button>
        </div>`).join("");

      this._body().innerHTML = `
        <div class="card"><h3>倉庫道具</h3>
          <div class="list">${itemRows || `<p class="muted">倉庫沒有道具。</p>`}</div>
          <div class="row" style="margin-top:10px">
            <button class="btn ghost small" id="deposit-item">從背包存入道具</button>
          </div></div>
        <div class="card"><h3>倉庫裝備</h3>
          <div class="list">${eqRows || `<p class="muted">倉庫沒有裝備。</p>`}</div>
          <div class="row" style="margin-top:10px">
            <button class="btn ghost small" id="deposit-eq">從背包存入裝備</button>
          </div></div>`;

      const reload = () => this._drawStorage();

      this._body().querySelectorAll("[data-withdraw-item]").forEach((b) => {
        b.onclick = async () => {
          const qty = num(`取出幾個「${b.dataset.name}」？`, 1);
          if (qty == null) return;
          b.disabled = true;
          try { await API.withdraw({ item_id: b.dataset.withdrawItem, qty }); App.toast("已取出"); reload(); }
          catch (e) { App.toast(e.detail || "取出失敗", true); b.disabled = false; }
        };
      });
      this._body().querySelectorAll("[data-withdraw-eq]").forEach((b) => {
        b.onclick = async () => {
          b.disabled = true;
          try { await API.withdraw({ equipment_instance_id: b.dataset.withdrawEq }); App.toast("已取出"); reload(); }
          catch (e) { App.toast(e.detail || "取出失敗", true); b.disabled = false; }
        };
      });
      document.querySelector("#deposit-item").onclick = () => this._depositItem(reload);
      document.querySelector("#deposit-eq").onclick = () => this._depositEq(reload);
    },

    async _depositItem(reload) {
      let inv;
      try { inv = await API.inventory(S.char.id); } catch (e) { App.toast(e.detail || "載入失敗", true); return; }
      const ids = Object.keys(inv.items || {});
      if (!ids.length) { App.toast("背包沒有道具", true); return; }
      const list = ids.map((id, i) => `${i + 1}. ${itemName(id)} ×${inv.items[id]}`).join("\n");
      const pick = prompt(`要存哪個道具？輸入編號：\n${list}`, "1");
      if (pick == null) return;
      const idx = Math.floor(Number(pick)) - 1;
      if (idx < 0 || idx >= ids.length) { App.toast("編號不對", true); return; }
      const qty = num(`存幾個「${itemName(ids[idx])}」？`, 1);
      if (qty == null) return;
      try { await API.deposit({ item_id: ids[idx], qty }); App.toast("已存入"); reload(); }
      catch (e) { App.toast(e.detail || "存入失敗", true); }
    },

    async _depositEq(reload) {
      let inv;
      try { inv = await API.inventory(S.char.id); } catch (e) { App.toast(e.detail || "載入失敗", true); return; }
      const eqs = (inv.equipment || []).filter((x) => x.equipped_slot == null);
      if (!eqs.length) { App.toast("背包沒有可存的裝備", true); return; }
      const list = eqs.map((x, i) => `${i + 1}. ${eqName(x.equipment_id)}${x.refine ? ` +${x.refine}` : ""}`).join("\n");
      const pick = prompt(`要存哪件裝備？輸入編號：\n${list}`, "1");
      if (pick == null) return;
      const idx = Math.floor(Number(pick)) - 1;
      if (idx < 0 || idx >= eqs.length) { App.toast("編號不對", true); return; }
      try { await API.deposit({ equipment_instance_id: eqs[idx].id }); App.toast("已存入"); reload(); }
      catch (e) { App.toast(e.detail || "存入失敗", true); }
    },
  };
})();
