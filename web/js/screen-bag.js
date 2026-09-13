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
      const isMaterial = (id) => S.catalog?.items?.[id]?.kind === "material";

      // 每張已鑲嵌的卡片鑲在哪些裝備上
      const socketedIn = {};
      for (const inst of inv.equipment || []) {
        for (const cid of inst.card_ids || []) {
          const tag = `${eqName(inst.equipment_id)}${inst.refine ? ` +${inst.refine}` : ""}`;
          (socketedIn[cid] = socketedIn[cid] || []).push(tag);
        }
      }

      const itemRow = ([id, qty]) => {
        const d = itemDesc(id);
        return `
        <div class="item">
          <div>${esc(itemName(id))}<div class="sub">×${qty}${d ? "　" + esc(d) : ""}</div></div>
          <div class="row tight">
            <button class="btn small" data-deposit-item="${id}" data-name="${esc(itemName(id))}">存</button>
            <button class="btn small" data-sell="${id}" data-name="${esc(itemName(id))}">賣</button>
          </div>
        </div>`;
      };
      const nonCardEntries = Object.entries(items).filter(([id]) => !isCard(id));
      const itemRows = nonCardEntries.filter(([id]) => !isMaterial(id)).map(itemRow).join("");
      const materialRows = nonCardEntries.filter(([id]) => isMaterial(id)).map(itemRow).join("");

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
          ${held > 0 ? `<button class="btn small" data-deposit-item="${id}" data-name="${esc(itemName(id))}">存</button>` : ""}
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
        .slice()
        .sort((a, b) => (b.equipped_slot != null) - (a.equipped_slot != null))
        .map((inst) => {
          const equipped = inst.equipped_slot != null;
          const cards = (inst.card_ids || []).map((c) => {
            const fx = cardDesc(c);
            return `${itemName(c)}${fx ? `（${fx}）` : ""}`;
          }).join("、");
          const slotZh = equipped ? `　裝備中（${SLOT_ZH[inst.equipped_slot] || inst.equipped_slot}）` : "";
          const worn = !equipped ? (wornBySlot[slotOf(inst.equipment_id)] || []) : [];
          const wornLine = worn.length
            ? `<div class="sub" style="color:var(--muted)">目前穿：${esc(worn.join("、"))}</div>`
            : (!equipped && slotOf(inst.equipment_id)
              ? `<div class="sub" style="color:var(--muted)">目前這個部位沒穿東西</div>` : "");
          const def = S.catalog?.equipment?.[inst.equipment_id];
          const canRefine = def && def.refinable !== false && (inst.refine || 0) < 10;
          const freeSockets = (def?.card_slots || 0) - (inst.card_ids || []).length;
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
              ${freeSockets > 0 ? `<button class="btn small" data-socket="${inst.id}" data-eqslot="${slotOf(inst.equipment_id)}">鑲卡</button>` : ""}
              ${(inst.card_ids || []).length ? `<button class="btn small" data-uncard="${inst.id}">卸卡</button>` : ""}
              ${equipped ? "" : `<button class="btn small" data-deposit-eq="${inst.id}" data-name="${esc(eqName(inst.equipment_id))}">存入倉庫</button>`}
              ${equipped ? "" : `<button class="btn small" data-sell-eq="${inst.id}" data-name="${esc(eqName(inst.equipment_id))}">賣出</button>`}
            </div>
          </div>
        </div>`;
        }).join("");

      const open = this._open || (this._open = {});
      const itemCount = nonCardEntries.filter(([id]) => !isMaterial(id)).length;
      const materialCount = nonCardEntries.filter(([id]) => isMaterial(id)).length;
      const eqCount = (inv.equipment || [])
        .filter((inst) => !this._bagSlot || slotOf(inst.equipment_id) === this._bagSlot).length;
      const sec = (key, title, count, inner) => `
        <details class="card bag-sec" data-sec="${key}"${open[key] ? " open" : ""}>
          <summary>${title}<span class="bag-sec-count">${count}</span></summary>
          <div class="bag-sec-body">${inner}</div>
        </details>`;

      this._body().innerHTML =
        sec("items", "道具", itemCount,
          `<div class="list">${itemRows || `<p class="muted">背包沒有道具。</p>`}</div>`)
        + sec("materials", "材料", materialCount,
          `<div class="list">${materialRows || `<p class="muted">背包沒有材料。</p>`}</div>`)
        + sec("cards", "卡片", cardIds.length,
          `<div class="list">${cardRows || `<p class="muted">背包沒有卡片。</p>`}</div>`)
        + sec("eq", "裝備", eqCount,
          `<div class="row" style="margin-bottom:8px">
             <select id="bag-slot" style="flex:1">${slotOptions}</select>
           </div>
           <div class="list">${eqRows || `<p class="muted">${this._bagSlot ? "這個部位沒有裝備。" : "背包沒有裝備。"}</p>`}</div>`);

      this._body().querySelectorAll("details[data-sec]").forEach((d) => {
        d.ontoggle = () => { open[d.dataset.sec] = d.open; };
      });

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
          const id = Number(b.dataset.sellEq);
          const name = b.dataset.name;
          const clicked = (inv.equipment || []).find((x) => x.id === id);
          // 同 ID、未精煉、未鑲卡、不在身上的才算「同款」可批次賣
          const plain = (x) => x.equipped_slot == null && !x.refine
            && (!x.card_ids || x.card_ids.length === 0);
          const same = clicked && plain(clicked)
            ? (inv.equipment || []).filter((x) => x.equipment_id === clicked.equipment_id && plain(x))
            : [];

          let ids;
          if (same.length > 1) {
            const raw = prompt(
              `你有 ${same.length} 件「${name}」（未精煉、未鑲卡）。\n要賣幾件？輸入 1～${same.length}，或 0 取消：`,
              String(same.length),
            );
            if (raw == null) return;
            const n = Math.floor(Number(raw));
            if (!Number.isFinite(n) || n <= 0) return;
            ids = same.slice(0, Math.min(n, same.length)).map((x) => x.id);
          } else {
            if (!confirm(`確定賣出「${name}」？賣掉就拿不回來了。`)) return;
            ids = [id];
          }

          b.disabled = true;
          try {
            const r = await API.sell({ equipment_instance_ids: ids });
            const cnt = r && r.count ? r.count : ids.length;
            App.toast(`賣了 ${name} ×${cnt}${r && r.gained != null ? `（+${r.gained}z）` : ""}`);
            await this._reloadHeader();
            reload();
          } catch (e) { App.toast(e.detail || "販售失敗", true); b.disabled = false; }
        };
      });
      this._body().querySelectorAll("[data-deposit-item]").forEach((b) => {
        b.onclick = async () => {
          const qty = num(`存幾個「${b.dataset.name}」進倉庫？`, 1);
          if (qty == null) return;
          b.disabled = true;
          try {
            await API.deposit({ item_id: b.dataset.depositItem, qty });
            App.toast(`存了 ${b.dataset.name} ×${qty} 進倉庫`);
            reload();
          } catch (e) { App.toast(e.detail || "存入失敗", true); b.disabled = false; }
        };
      });
      this._body().querySelectorAll("[data-deposit-eq]").forEach((b) => {
        b.onclick = async () => {
          const id = Number(b.dataset.depositEq);
          const name = b.dataset.name;
          const ids = this._sameStackIds(inv.equipment || [], id, `存幾件「${name}」（未精煉、未鑲卡）進倉庫？`);
          if (ids == null) return;
          b.disabled = true;
          try {
            for (const eid of ids) await API.deposit({ equipment_instance_id: eid });
            App.toast(`存了 ${name} ×${ids.length} 進倉庫`);
            reload();
          } catch (e) { App.toast(e.detail || "存入失敗", true); b.disabled = false; }
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
        b.onclick = () => {
          const inst = (inv.equipment || []).find((x) => x.id === Number(b.dataset.refine));
          if (inst) this._openRefine(inst);
        };
      });
      this._body().querySelectorAll("[data-uncard]").forEach((b) => {
        b.onclick = async () => {
          const inst = (inv.equipment || []).find((x) => x.id === Number(b.dataset.uncard));
          const cards = (inst && inst.card_ids) || [];
          if (!cards.length) return;
          let idx = 0;
          if (cards.length > 1) {
            const list = cards.map((c, i) => `${i + 1}. ${itemName(c)}`).join("\n");
            const pick = prompt(`要卸哪張卡？輸入編號：\n${list}`, "1");
            if (pick == null) return;
            idx = Math.floor(Number(pick)) - 1;
            if (idx < 0 || idx >= cards.length) { App.toast("編號不對", true); return; }
          }
          if (!confirm(`花 20000z 取出「${itemName(cards[idx])}」？\n60% 成功；失敗只損失 20000z，卡片和裝備都留著。`)) return;
          b.disabled = true;
          try {
            const r = await API.uncard(S.char.id, Number(b.dataset.uncard), idx);
            App.toast(r.message || (r.success ? "取卡成功" : "取卡失敗"), !r.success);
            await this._reloadHeader();
            reload();
          } catch (e) { App.toast(e.detail || "卸卡失敗", true); b.disabled = false; }
        };
      });
      this._body().querySelectorAll("[data-socket]").forEach((b) => {
        b.onclick = async () => {
          const cardId = this._pickCard(inv.items || {}, b.dataset.eqslot);
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

    // 同款（同 equipment_id、未精煉、未鑲卡、不在身上）裝備一次選幾件一起處理，
    // 不用一件一件點。單件就直接回那一件，不用另外問。
    _sameStackIds(equipment, clickedId, promptLabel) {
      const clicked = equipment.find((x) => x.id === clickedId);
      const plain = (x) => x.equipped_slot == null && !x.refine
        && (!x.card_ids || x.card_ids.length === 0);
      const same = clicked && plain(clicked)
        ? equipment.filter((x) => x.equipment_id === clicked.equipment_id && plain(x))
        : [];
      if (same.length <= 1) return [clickedId];
      const raw = prompt(`你有 ${same.length} 件（未精煉、未鑲卡）。\n${promptLabel}輸入 1～${same.length}，或 0 取消：`,
        String(same.length));
      if (raw == null) return null;
      const n = Math.floor(Number(raw));
      if (!Number.isFinite(n) || n <= 0) return null;
      return same.slice(0, Math.min(n, same.length)).map((x) => x.id);
    },

    _pickCard(items, eqSlot) {
      const slotZh = SLOT_ZH[eqSlot] || eqSlot;
      const cards = Object.keys(items).filter(
        (id) => S.catalog?.cards?.[id] && S.catalog.cards[id].slot === eqSlot,
      );
      if (!cards.length) { App.toast(`背包沒有可鑲「${slotZh}」的卡片`, true); return null; }
      const list = cards.map((id, i) => `${i + 1}. ${itemName(id)} ×${items[id]}（${slotZh}）`).join("\n");
      const pick = prompt(`要鑲哪張卡？這件裝備吃「${slotZh}」卡。輸入編號：\n${list}`, "1");
      if (pick == null) return null;
      const idx = Math.floor(Number(pick)) - 1;
      if (idx < 0 || idx >= cards.length) { App.toast("編號不對", true); return null; }
      return cards[idx];
    },

    // ---------- 精煉小視窗 ----------
    _openRefine(inst) {
      this._refLog = [];
      this._refBlocked = false;
      this._drawRefine(inst.id);
    },

    async _drawRefine(instId) {
      let inv;
      try { inv = await API.inventory(S.char.id); }
      catch (e) { this._drawBag(); return; }
      const inst = (inv.equipment || []).find((x) => x.id === instId);
      const def = inst && S.catalog?.equipment?.[inst.equipment_id];
      if (!inst || !def) { this._drawBag(); return; }
      const isWeapon = def.slot === "weapon";
      const oreName = isWeapon ? "神之金屬" : "鋁";
      const oreHave = (inv.items || {})[isWeapon ? "oridecon" : "elunium"] || 0;
      const cur = inst.refine || 0;
      const normalZeny = (cur + 1) * 200;
      const maxed = cur >= 10;
      const disabled = maxed || this._refBlocked;

      const REF_PER_LV = { atk: 2, matk: 2, defense: 1, mdef: 1, max_hp: 15, flee: 1, hit: 1, crit: 1 };
      const bonusAt = (r) => Object.keys(def.stats || {})
        .filter((k) => REF_PER_LV[k])
        .map((k) => `${STAT_ZH[k] || k} +${REF_PER_LV[k] * r}`).join("、");
      const curBonus = cur > 0 ? bonusAt(cur) : "";
      const nextBonus = maxed ? "" : bonusAt(cur + 1);

      this._body().innerHTML = `
        <div class="card">
          <div class="section-title"><h3>精煉 ${esc(eqName(inst.equipment_id))}</h3>
            <span class="pill good">+${cur}</span></div>
          <div class="sub">材料：${oreName} ×1（持有 ${oreHave}）　Zeny ${S.char.zeny}</div>
          ${curBonus ? `<div class="sub" style="color:var(--good)">目前精煉加成：${curBonus}</div>` : ""}
          ${nextBonus ? `<div class="sub" style="color:var(--muted)">升到 +${cur + 1}：${nextBonus}</div>` : ""}
          <div class="row tight" style="margin-top:10px">
            <button class="btn small ${disabled ? "" : "primary"}" id="ref-normal" ${disabled ? "disabled" : ""}>普通（Zeny ${normalZeny}）</button>
            <button class="btn small" id="ref-random" ${disabled ? "disabled" : ""}>隨機（Zeny ${normalZeny * 10}）</button>
          </div>
          ${maxed ? `<p class="pill good" style="margin-top:8px">已達 +10</p>` : ""}
          ${this._refBlocked ? `<p class="pill bad" style="margin-top:8px">材料或 Zeny 不足，補充後再回來</p>` : ""}
          <div class="log" style="height:150px;margin-top:10px">${
            (this._refLog || []).slice(-12).join("\n")
            || "<span class='dim'>選一種模式開始精煉，結果會列在這裡。</span>"}</div>
          <div class="row" style="margin-top:10px">
            <button class="btn ghost small" id="ref-back">返回背包</button>
          </div>
        </div>`;

      this._body().querySelector("#ref-back").onclick = () => { this._drawBag(); };
      const attempt = async (mode) => {
        this._body().querySelectorAll("#ref-normal,#ref-random").forEach((x) => (x.disabled = true));
        try {
          const r = await API.refine(S.char.id, instId, mode);
          this._refLog.push(`<span class="${r.success ? "hit" : "crit"}">${
            esc(r.message || (r.success ? `成功 +${r.refine}` : `失敗 → +${r.refine}`))}</span>`);
          await this._reloadHeader();
        } catch (e) {
          this._refLog.push(`<span class="crit">${esc(e.detail || "精煉中止")}</span>`);
          this._refBlocked = true;
        }
        this._drawRefine(instId);
      };
      const nb = this._body().querySelector("#ref-normal");
      const rb = this._body().querySelector("#ref-random");
      if (nb && !disabled) nb.onclick = () => attempt("normal");
      if (rb && !disabled) rb.onclick = () => attempt("random");
    },

    // ---------- 倉庫 ----------
    async _drawStorage() {
      let st;
      try { st = await API.storage(); }
      catch (e) { if (this._stale("storage")) return; this._body().innerHTML = `<div class="card">${esc(e.detail || "載入失敗")}</div>`; return; }
      if (this._stale("storage")) return;

      const items = st.items || {};
      const isMaterial = (id) => S.catalog?.items?.[id]?.kind === "material";
      const itemRow = ([id, qty]) => `
        <div class="item">
          <div>${esc(itemName(id))}<div class="sub">×${qty}</div></div>
          <button class="btn small" data-withdraw-item="${id}" data-name="${esc(itemName(id))}">取出</button>
        </div>`;
      const itemEntries = Object.entries(items);
      const itemRows = itemEntries.filter(([id]) => !isMaterial(id)).map(itemRow).join("");
      const materialRows = itemEntries.filter(([id]) => isMaterial(id)).map(itemRow).join("");

      // 同款（同 equipment_id、未精煉、未鑲卡）裝備合併成一列顯示數量，不用捲一長串
      // 一模一樣的東西；有精煉或鑲卡的各自獨一無二，還是分開列。
      const eqList = st.equipment || [];
      const plainEq = (x) => !x.refine && (!x.card_ids || x.card_ids.length === 0);
      const grouped = {};
      const uniqueRows = [];
      for (const inst of eqList) {
        if (plainEq(inst)) {
          (grouped[inst.equipment_id] = grouped[inst.equipment_id] || []).push(inst);
        } else {
          uniqueRows.push(`
        <div class="item">
          <div>${esc(eqName(inst.equipment_id))} <span class="pill good">+${inst.refine || 0}</span>
            <div class="sub">${esc(eqSlot(inst.equipment_id) || "")}</div></div>
          <button class="btn small" data-withdraw-eq="${inst.id}">取出</button>
        </div>`);
        }
      }
      const groupRows = Object.entries(grouped).map(([eqId, insts]) => `
        <div class="item">
          <div>${esc(eqName(eqId))}${insts.length > 1 ? `<span class="pill" style="margin-left:6px">×${insts.length}</span>` : ""}
            <div class="sub">${esc(eqSlot(eqId) || "")}</div></div>
          <button class="btn small" data-withdraw-eq="${insts[0].id}" data-eq-group="${eqId}">取出</button>
        </div>`);
      const eqRows = [...groupRows, ...uniqueRows].join("");

      this._body().innerHTML = `
        <div class="card"><h3>倉庫道具</h3>
          <div class="list">${itemRows || `<p class="muted">倉庫沒有道具。</p>`}</div></div>
        <div class="card"><h3>倉庫材料</h3>
          <div class="list">${materialRows || `<p class="muted">倉庫沒有材料。</p>`}</div></div>
        <div class="card"><h3>倉庫裝備</h3>
          <div class="list">${eqRows || `<p class="muted">倉庫沒有裝備。</p>`}</div></div>
        <p class="sub">要存東西進倉庫，去「背包」頁面，每個道具/裝備旁邊都有「存」的按鈕。</p>`;

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
          const eqId = b.dataset.eqGroup;
          const name = eqName(eqId || "");
          let ids = [Number(b.dataset.withdrawEq)];
          const stack = eqId ? grouped[eqId] : null;
          if (stack && stack.length > 1) {
            const raw = prompt(`倉庫有 ${stack.length} 件「${name}」（未精煉、未鑲卡）。\n要取出幾件？輸入 1～${stack.length}，或 0 取消：`,
              String(stack.length));
            if (raw == null) return;
            const n = Math.floor(Number(raw));
            if (!Number.isFinite(n) || n <= 0) return;
            ids = stack.slice(0, Math.min(n, stack.length)).map((x) => x.id);
          }
          b.disabled = true;
          try {
            for (const id of ids) await API.withdraw({ equipment_instance_id: id });
            App.toast(`取出 ×${ids.length}`);
            reload();
          } catch (e) { App.toast(e.detail || "取出失敗", true); b.disabled = false; }
        };
      });
    },
  };
})();
