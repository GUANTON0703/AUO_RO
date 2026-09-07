// ROtxt web — screen render modules.
// Each screen: { mount() }  — builds #view. Some also expose render(data) for live updates.
// Scaffold provides: home, hunt.  TODO (agents): build, shop, social, more, inv, gm...

const S = App.state;
const view = () => document.querySelector("#view");
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

// exp curve — mirrors server/progression/levels.py
const Curve = {
  baseNext: (lvl) => Math.round(30 * Math.pow(lvl, 2.4) + 40 * lvl + 30),
  jobNext: (jl, tier) => {
    const m = { novice: 0.6, first: 1.0, second: 1.8 }[tier] ?? 1.0;
    return Math.round((20 * Math.pow(jl, 2.2) + 30 * jl + 20) * m);
  },
};
const jobName = (id) => S.catalog?.jobs?.[id]?.name || id;
const jobTier = (id) => S.catalog?.jobs?.[id]?.tier || "first";
const monName = (id) => S.catalog?.monsters?.[id]?.name || S.catalog?.mvps?.[id]?.name || id;
const mapName = (id) => S.catalog?.maps?.[id]?.name || id;
const itemName = (id) =>
  S.catalog?.items?.[id]?.name || S.catalog?.equipment?.[id]?.name ||
  S.catalog?.cards?.[id]?.name || id;

function bar(cur, max, cls) {
  const pct = Math.max(0, Math.min(100, (cur / Math.max(1, max)) * 100));
  return `<div class="bar ${cls || ""}"><i style="width:${pct}%"></i></div>`;
}

// ---- 內容說明（給商店 / 背包 / 交易顯示「這東西幹嘛用」）----
const SLOT_ZH = { weapon: "武器", offhand: "副手", head: "頭部", armor: "鎧甲",
  garment: "披肩", shoes: "鞋子", accessory: "飾品",
  accessory1: "飾品（左）", accessory2: "飾品（右）", shield: "盾" };
// 狀態頁裝備欄顯示順序
const SLOT_ORDER = [
  ["weapon", "武器"], ["offhand", "副手"], ["head", "頭部"], ["armor", "鎧甲"],
  ["garment", "披肩"], ["shoes", "鞋子"],
  ["accessory1", "飾品（左）"], ["accessory2", "飾品（右）"],
];
const STAT_ZH = { str: "力量", agi: "敏捷", vit: "體質", int: "智力", dex: "靈巧",
  luk: "幸運", atk: "攻擊", matk: "魔攻", def: "防禦", mdef: "魔防", hit: "命中",
  flee: "迴避", crit: "爆擊", aspd: "攻速", max_hp: "HP上限", max_sp: "SP上限",
  defense: "防禦", magic_defense: "魔防", attack: "攻擊", magic_attack: "魔攻",
  hp: "HP上限", sp: "SP上限", accuracy: "命中", evasion: "迴避", critical: "爆擊" };

const ELEM_ZH = { neutral: "無", water: "水", earth: "地", fire: "火", wind: "風",
  poison: "毒", holy: "聖", shadow: "暗", ghost: "念", undead: "不死" };
const RACE_ZH = { formless: "無形", undead: "不死", animal: "動物", plant: "植物",
  insect: "昆蟲", fish: "魚貝", demon: "惡魔", demihuman: "人形", angel: "天使",
  dragon: "龍" };
const PROC_ZH = { stun: "暈眩", poison: "中毒", blind: "致盲", silence: "沉默",
  freeze: "冰凍", sleep: "睡眠", curse: "詛咒", bleed: "流血" };

function effectText(e) {
  if (!e) return "";
  if (e.type === "heal_hp") return `回復 HP ${e.amount}`;
  if (e.type === "heal_sp") return `回復 SP ${e.amount}`;
  if (e.type === "teleport") return "隨機傳送到附近";
  if (e.type === "flat_stat") return `${STAT_ZH[e.stat] || e.stat} +${e.amount}`;
  if (e.type === "pct_stat") return `${STAT_ZH[e.stat] || e.stat} +${e.amount}%`;
  if (e.type === "percent_stat") return `${STAT_ZH[e.stat] || e.stat} +${e.pct}%`;
  if (e.type === "element_resist") return `${ELEM_ZH[e.element] || e.element}屬性抗性 +${e.pct}%`;
  if (e.type === "race_damage") return `對${RACE_ZH[e.race] || e.race}傷害 +${e.pct}%`;
  if (e.type === "on_hit_proc") return `攻擊 ${e.chance_pct}% 機率${PROC_ZH[e.effect] || e.effect}`;
  return e.type;
}

// 道具說明字串
function itemDesc(id) {
  const it = S.catalog?.items?.[id];
  if (!it) return "";
  const fx = (it.effects || []).map(effectText).filter(Boolean).join("、");
  return fx || (it.kind === "material" ? "素材（賣錢 / 精煉用）" : "");
}

// 裝備 / 卡片說明字串
function gearDesc(id) {
  const eq = S.catalog?.equipment?.[id];
  if (eq) {
    const parts = [];
    parts.push(SLOT_ZH[eq.slot] || eq.slot);
    const st = Object.entries(eq.stats || {}).map(([k, v]) =>
      `${STAT_ZH[k] || k} ${v > 0 ? "+" : ""}${v}`);
    if (st.length) parts.push(st.join(" "));
    if (eq.required_level > 1) parts.push(`需 Lv ${eq.required_level}`);
    const jobs = eq.job_ids || [];
    parts.push(jobs.length ? "限 " + jobs.map(jobName).join("/") : "全職業");
    if (eq.card_slots) parts.push(`${eq.card_slots} 卡槽`);
    return parts.join("・");
  }
  const cd = S.catalog?.cards?.[id];
  if (cd) {
    const fx = (cd.effects || []).map(effectText).filter(Boolean).join("、");
    return `卡片・插${SLOT_ZH[cd.slot] || cd.slot}${fx ? "・" + fx : ""}`;
  }
  return "";
}

// 卡片說明：效果 + 可鑲部位（背包卡片區用）
function cardDesc(id) {
  const cd = S.catalog?.cards?.[id];
  if (!cd) return "";
  const fx = (cd.effects || []).map(effectText).filter(Boolean).join("、");
  return `${fx || "特殊效果"}　可鑲：${SLOT_ZH[cd.slot] || cd.slot}`;
}

const Screens = {};

// ---------- 狀態（首頁）----------
Screens.home = {
  async mount() {
    this._stopDrip();
    this._queue = [];
    this._shown = [];
    this._lastBatch = null;
    this._hunting = null;
    this._dripMs = 0;
    this._paceBudget = 0;
    this._curMon = null;
    this._sheet = await API.sheet(S.char.id).catch(() => null);
    S._sheet = this._sheet;
    this._strategy = await API.huntStrategy(S.char.id).catch(() => null);
    let status = null;
    try { status = await API.huntStatus(); } catch (e) { if (e.status !== 409) throw e; }
    // status 這一趟可能撿到裝備，所以裝備清單在它之後才抓
    this._inv = await API.inventory(S.char.id).catch(() => null);
    this._layout(status);
    if (status && !status.retreated) {
      this._ingest(status);
      this._drip();
      App.startHuntPoll();
    }
  },

  // 每 poll 呼叫：掛機狀態沒切換就只更新數字、不碰戰鬥紀錄；切換才整個重畫
  render(status) {
    if (S.view !== "home") return;
    const hunting = !!(status && !status.retreated);
    if (hunting !== this._hunting || (status && status.retreated)) {
      this._layout(status);
      if (hunting) { this._ingest(status); this._drip(); }
      else this._stopDrip();
      return;
    }
    if (hunting) { this._ingest(status); this._updateKV(status); }
  },

  _dripInterval() {
    // 每批事件攤開填滿它代表的遊戲內時間，這樣兩批之間不會有一段空白。
    // 沒有 pace 資訊時退回用攻擊速度估。
    if (this._dripMs) return this._dripMs;
    const aspd = (this._sheet && this._sheet.aspd) || 100;
    return Math.min(1400, Math.max(150, Math.round(100000 / Math.max(aspd, 50))));
  },
  _stopDrip() { if (this._dripTimer) { clearTimeout(this._dripTimer); this._dripTimer = null; } },
  _recalcDrip() {
    const n = this._queue.length;
    if (!n) { this._dripMs = 0; this._paceBudget = 0; return; }
    this._dripMs = this._paceBudget > 0
      ? Math.min(1600, Math.max(300, Math.round((this._paceBudget * 1000) / n)))
      : 0;
  },
  _heartbeat() {
    const f = ["⡿", "⣟", "⣯", "⣷", "⣾", "⣽", "⣻", "⢿"];
    this._pulse = ((this._pulse || 0) + 1) % f.length;
    const mon = this._curMon ? esc(monName(this._curMon)) : "怪物";
    return `<span class="dim">${f[this._pulse]} 與 ${mon} 交戰中…</span>`;
  },
  _drip() {
    this._stopDrip();
    const box = document.querySelector("#huntlog");
    if (!box || S.view !== "home") return;
    if (this._queue.length) {
      this._shown.push(this._queue.shift());
      while (this._shown.length > 60) this._shown.shift();
      box.innerHTML = this._shown.join("\n");
      box.scrollTop = box.scrollHeight;
      this._paceBudget = Math.max(0, (this._paceBudget || 0) - this._dripMs / 1000);
      this._recalcDrip();
    } else if (!this._shown.length) {
      box.innerHTML = "<span class='dim'>搜尋目標中…</span>";
    } else if (this._hunting) {
      // 佇列清空、還在掛機 → 顯示一個跳動的「交戰中」，畫面才不會像卡住
      box.innerHTML = this._shown.join("\n") + "\n" + this._heartbeat();
      box.scrollTop = box.scrollHeight;
    }
    let wait;
    if (this._queue.length > 40) wait = 50;
    else if (this._queue.length) wait = this._dripInterval();
    else wait = 900;                        // 心跳更新節奏
    this._dripTimer = setTimeout(() => this._drip(), wait);
  },
  _ingest(status) {
    if (!status || status.retreated) return;
    if (status.monster_id) this._curMon = status.monster_id;
    if (!status.batch_id || status.batch_id === this._lastBatch) return;
    this._lastBatch = status.batch_id;
    const lines = this._logLines(status.events || []);
    const drops = status.drops || {};
    const dk = Object.keys(drops);
    if (dk.length) {
      lines.push(`<span class="kill">　取得 ${dk.map((k) =>
        `${esc(itemName(k))} ×${drops[k]}`).join("、")}</span>`);
      // 撿到裝備 → 更新狀態頁的裝備欄
      if (dk.some((k) => S.catalog?.equipment?.[k])) this._refreshEquip();
    }
    if (status.offline || lines.length > 30) {          // 離線大批次直接倒完
      this._queue.length = 0;
      this._dripMs = 0;
      this._paceBudget = 0;
      this._shown.push(...lines);
      while (this._shown.length > 60) this._shown.shift();
      const box = document.querySelector("#huntlog");
      if (box) { box.innerHTML = this._shown.join("\n"); box.scrollTop = box.scrollHeight; }
    } else {
      this._queue.push(...lines);
      // 每批帶來的遊戲內時間累加進「攤開預算」，再平均分給佇列裡所有還沒跳出的行，
      // 這樣就算新批在舊批還沒跳完時進來，整體節奏也不會忽快忽慢。
      this._paceBudget = (this._paceBudget || 0) + (Number(status.pace_seconds) || 0);
      this._recalcDrip();
    }
  },

  _updateKV(status) {
    const c = S.char, sheet = this._sheet || {};
    const tier = jobTier(c.job_id);
    const hp = status?.character?.hunt_hp ?? sheet.hunt_hp ?? sheet.max_hp ?? 0;
    const sp = status?.character?.hunt_sp ?? sheet.hunt_sp ?? sheet.max_sp ?? 0;
    const setT = (id, v) => { const el = document.querySelector(id); if (el) el.textContent = v; };
    const setW = (id, cur, max) => { const el = document.querySelector(id);
      if (el) el.style.width = Math.max(0, Math.min(100, (cur / Math.max(1, max)) * 100)) + "%"; };
    setT("#hm-btext", `${c.base_exp} / ${Curve.baseNext(c.base_level)}`);
    setW("#hm-bbar", c.base_exp, Curve.baseNext(c.base_level));
    setT("#hm-jtext", `${c.job_exp} / ${Curve.jobNext(c.job_level, tier)}`);
    setW("#hm-jbar", c.job_exp, Curve.jobNext(c.job_level, tier));
    setT("#hm-hptext", `${hp} / ${sheet.max_hp ?? "?"}`);
    setW("#hm-hpbar", hp, sheet.max_hp ?? 1);
    setT("#hm-sptext", `${sp} / ${sheet.max_sp ?? "?"}`);
    setW("#hm-spbar", sp, sheet.max_sp ?? 1);
    setT("#hm-zeny", c.zeny);
    setT("#hk-mon", monName(status.monster_id));
    setT("#hk-kills", status.kills);
    setT("#hk-exp", `+${status.base_exp} / +${status.job_exp}`);
    setT("#hk-zeny", `+${status.zeny}`);
    setT("#hk-time", Math.floor(App.huntSecsShown()) + " 秒");
    const lj = JSON.stringify(status.loot || {});
    if (lj !== this._lootJson) {
      this._lootJson = lj;
      const lb = document.querySelector("#loot-box");
      if (lb) { lb.innerHTML = this._lootHtml(status.loot); this._wireLoot(); }
    }
  },

  _lootHtml(loot) {
    const held = loot || {};
    const sell = new Set((this._strategy && this._strategy.sell_item_ids) || []);
    const sellable = (id) => (S.catalog?.items?.[id]?.npc_sell || 0) > 0;
    // 撿到的 + 已被自動賣掉的（清單裡有但背包已清空）都列出來，才能取消勾選
    const ids = [...new Set([...Object.keys(held), ...sell])];
    if (!ids.length) return `<p class="muted" style="margin-top:8px">本場還沒撿到東西</p>`;
    return `<div style="margin-top:8px"><div class="sub">本場撿到（勾 = 之後自動賣掉）</div>` +
      ids.map((id) => {
        const qty = held[id] || 0;
        const label = qty > 0 ? `${esc(itemName(id))} ×${qty}`
          : `${esc(itemName(id))}（已自動賣出）`;
        return `
        <label class="kv" style="cursor:pointer">
          <span>${label}</span>
          ${sellable(id) || sell.has(id)
            ? `<input type="checkbox" data-sell="${esc(id)}" style="width:auto" ${sell.has(id) ? "checked" : ""}>`
            : `<span class="dim" style="font-size:.85em">不可賣</span>`}
        </label>`;
      }).join("") + `</div>`;
  },
  _wireLoot() {
    document.querySelectorAll("#loot-box [data-sell]").forEach((cb) => {
      cb.onchange = async () => {
        const id = cb.dataset.sell;
        const strat = this._strategy || (this._strategy = {});
        const prev = strat.sell_item_ids ? [...strat.sell_item_ids] : [];
        const set = new Set(prev);
        cb.checked ? set.add(id) : set.delete(id);
        strat.sell_item_ids = [...set];
        try {
          await API.setHuntStrategy(S.char.id, strat);
          App.toast(cb.checked ? "已設為自動賣" : "取消自動賣");
        } catch (e) {
          strat.sell_item_ids = prev;
          cb.checked = !cb.checked;
          App.toast(e.detail || "失敗", true);
        }
      };
    });
  },

  _equipHtml(inv) {
    const eqs = (inv && inv.equipment) || [];
    const bySlot = {};
    for (const e of eqs) if (e.equipped_slot) bySlot[e.equipped_slot] = e;
    const rows = SLOT_ORDER.map(([slot, zh]) => {
      const e = bySlot[slot];
      if (!e) {
        return `<div class="kv"><span class="k">${zh}</span>` +
          `<span class="dim">未裝備</span></div>`;
      }
      const rf = e.refine ? ` <span class="pill good">+${e.refine}</span>` : "";
      const def = S.catalog?.equipment?.[e.equipment_id];
      const n = def?.card_slots || 0;
      const cards = (e.card_ids || []).map((c) => esc(itemName(c)));
      let cardTxt = "";
      if (n) {
        const filled = cards.join("、");
        const empty = n - cards.length;
        cardTxt = `<div class="sub">卡：${filled || "－"}` +
          `${empty > 0 ? `（空 ${empty} 孔）` : ""}</div>`;
      }
      return `<div class="kv" style="align-items:flex-start"><span class="k">${zh}</span>` +
        `<span style="text-align:right">${esc(itemName(e.equipment_id))}${rf}${cardTxt}</span></div>`;
    }).join("");
    return `<div class="card" id="equip-box"><h3>裝備</h3>${rows}</div>`;
  },
  async _refreshEquip() {
    this._inv = await API.inventory(S.char.id).catch(() => this._inv);
    const box = document.querySelector("#equip-box");
    if (box && S.view === "home") box.outerHTML = this._equipHtml(this._inv);
  },

  _layout(status) {
    this._hunting = !!(status && !status.retreated);
    const c = S.char, sheet = this._sheet || {};
    const tier = jobTier(c.job_id);
    const hp = status?.character?.hunt_hp ?? sheet.hunt_hp ?? sheet.max_hp ?? 0;
    const sp = status?.character?.hunt_sp ?? sheet.hunt_sp ?? sheet.max_sp ?? 0;

    let html = `
      <div class="card">
        <div class="section-title"><h2>${esc(c.name)}</h2>
          <span class="pill">${esc(jobName(c.job_id))}</span></div>
        <div class="kv"><span class="k">Base Lv ${c.base_level}</span>
          <span id="hm-btext">${c.base_exp} / ${Curve.baseNext(c.base_level)}</span></div>
        <div class="bar exp"><i id="hm-bbar" style="width:${Math.min(100,(c.base_exp/Math.max(1,Curve.baseNext(c.base_level)))*100)}%"></i></div>
        <div class="kv"><span class="k">Job Lv ${c.job_level}</span>
          <span id="hm-jtext">${c.job_exp} / ${Curve.jobNext(c.job_level, tier)}</span></div>
        <div class="bar exp"><i id="hm-jbar" style="width:${Math.min(100,(c.job_exp/Math.max(1,Curve.jobNext(c.job_level,tier)))*100)}%"></i></div>
        <div class="kv"><span class="k">HP</span><span id="hm-hptext">${hp} / ${sheet.max_hp ?? "?"}</span></div>
        <div class="bar hp"><i id="hm-hpbar" style="width:${Math.min(100,(hp/Math.max(1,sheet.max_hp??1))*100)}%"></i></div>
        <div class="kv"><span class="k">SP</span><span id="hm-sptext">${sp} / ${sheet.max_sp ?? "?"}</span></div>
        <div class="bar sp"><i id="hm-spbar" style="width:${Math.min(100,(sp/Math.max(1,sheet.max_sp??1))*100)}%"></i></div>
        <div class="kv"><span class="k">Zeny</span><span id="hm-zeny">${c.zeny}</span></div>
        <div class="kv"><span class="k">地點</span><span>${esc(mapName(c.location_map))}</span></div>
      </div>
      ${this._equipHtml(this._inv)}`;

    if (this._hunting) {
      html += `
        <div class="card">
          <div class="section-title"><h3>掛機中</h3>
            <span class="pill good" id="hk-mon">${esc(monName(status.monster_id))}</span></div>
          <div class="kv"><span class="k">擊殺</span><span id="hk-kills">${status.kills}</span></div>
          <div class="kv"><span class="k">本場經驗</span><span id="hk-exp">+${status.base_exp} / +${status.job_exp}</span></div>
          <div class="kv"><span class="k">本場 Zeny</span><span id="hk-zeny">+${status.zeny}</span></div>
          <div class="kv"><span class="k">掛機時間</span><span id="hk-time">${Math.floor(App.huntSecsShown())} 秒</span></div>
          <div class="log" id="huntlog">${this._shown.join("\n") || "<span class='dim'>搜尋目標中…</span>"}</div>
          <div id="loot-box">${this._lootHtml(status.loot)}</div>
          <div class="row" style="margin-top:10px">
            <button class="btn block" id="btn-stop">停止掛機並結算</button>
          </div>
        </div>`;
    } else if (status && status.retreated) {
      html += `<div class="card"><h3>掛機結束</h3>
        <p>擊殺 ${status.kills}　經驗 +${status.base_exp}/${status.job_exp}　Zeny +${status.zeny}</p>
        <p class="pill bad">${esc(status.retreat_reason || "已撤退")}</p>
        <button class="btn primary block" onclick="App.navigate('hunt')" style="margin-top:8px">重新掛機</button>
        </div>`;
    } else {
      html += `<div class="card"><h3>沒有在掛機</h3>
        <button class="btn primary block" onclick="App.navigate('hunt')">去掛機</button></div>`;
    }
    view().innerHTML = html;
    this._lootJson = JSON.stringify((status && status.loot) || {});
    this._wireLoot();

    const stopBtn = document.querySelector("#btn-stop");
    if (stopBtn) stopBtn.onclick = async () => {
      stopBtn.disabled = true;
      try {
        const r = await API.huntStop();
        App.stopHuntPoll();
        this._stopDrip();
        App.toast(`結算：擊殺 ${r.kills}，經驗 +${r.base_exp}/${r.job_exp}`);
        await App.refreshChar();
        this._sheet = await API.sheet(S.char.id).catch(() => this._sheet);
        this._inv = await API.inventory(S.char.id).catch(() => this._inv);
        this._layout(null);
      } catch (e) { App.toast(e.detail || "停止失敗", true); stopBtn.disabled = false; }
    };
  },

  _logLines(events) {
    if (!events) return [];
    const out = [];
    const bbb = events.some((e) => ["attack", "skill", "kill"].includes(e.kind));
    for (const e of events) {
      if (e.kind === "attack") {
        if (!e.hit) out.push(`<span class="dim">  ${esc(e.actor)} 攻擊 ${esc(e.target)} → MISS</span>`);
        else out.push(`<span class="${e.crit ? "crit" : "hit"}">  ${esc(e.actor)} 攻擊 ${esc(e.target)} → ${e.damage}${e.crit ? " 暴擊!" : ""}</span>`);
      } else if (e.kind === "kill") {
        out.push(`<span class="kill">${esc(e.actor)} 擊倒了 ${esc(e.target)}</span>`);
      } else if (e.kind === "heal") {
        const how = e.source === "potion" ? "喝藥水" : "施放治療";
        out.push(`<span class="dim">  ${esc(e.actor)} ${how} 回復 ${e.amount}</span>`);
      } else if (e.kind === "kill_batch" && !bbb) {
        out.push(`<span class="kill">擊殺 ${esc(e.monster_name)} ×${e.count}　+經驗 ${e.base_exp}/${e.job_exp}　+Zeny ${e.zeny}</span>`);
      } else if (e.kind === "potion_used") {
        out.push(`<span class="dim">  使用 ${esc(itemName(e.item_id))} ×${e.count}（剩 ${e.remaining}）</span>`);
      } else if (e.kind === "find_monster") {
        out.push(`<span class="dim">正在尋找怪物…</span>`);
      } else if (e.kind === "retreat") {
        out.push(`<span class="dim">撤退：${esc(e.reason || "")}</span>`);
      }
    }
    return out.slice(-40);
  },
};

// ---------- 掛機設定 ----------
Screens.hunt = {
  async mount() {
    const bl = S.char.base_level;
    const maps = Object.values(S.catalog.maps)
      .filter((m) => bl >= (m.unlock_base_level || 1))
      .sort((a, b) => (a.unlock_base_level || 1) - (b.unlock_base_level || 1));
    this._picked = new Set();
    this._mapId = null;
    this._strategy = await API.huntStrategy(S.char.id).catch(() => ({}));

    let html = `<div class="card"><h3>選狩獵地圖</h3><div class="list" id="maplist">`;
    for (const m of maps) {
      html += `<button class="btn choice" data-map="${m.id}">
        ${esc(m.name)}<div class="sub">解鎖 Lv ${m.unlock_base_level || 1}
        ・${m.monster_ids.map(monName).join("、")}</div></button>`;
    }
    if (!maps.length) html += `<p class="muted">還沒有解鎖的地圖。</p>`;
    html += `</div></div><div id="monsterpick"></div>` + this._strategyCard();
    view().innerHTML = html;

    view().querySelectorAll("[data-map]").forEach((b) => {
      b.onclick = () => { this._selectMap(b.dataset.map); };
    });
    this._wireStrategy();
  },

  _strategyCard() {
    const s = this._strategy || {};
    const potions = Object.values(S.catalog.items || {})
      .filter((it) => (it.effects || []).some((e) => e.type === "heal_hp"));
    const opt = (list, sel) => list.map((it) =>
      `<option value="${it.id}"${it.id === sel ? " selected" : ""}>${esc(it.name)}</option>`).join("");
    return `
      <div class="card"><h3>掛機設定</h3>
        <label class="kv" style="cursor:pointer">
          <span>自動喝水</span>
          <input type="checkbox" id="st-autopot" style="width:auto" ${s.auto_potion !== false ? "checked" : ""}>
        </label>
        <div class="kv"><span class="k">血量低於</span>
          <span><input type="number" id="st-hppct" min="5" max="95" style="width:64px"
            value="${Math.round((s.potion_hp_pct ?? 0.5) * 100)}"> %　才喝</span></div>
        <label class="kv" style="cursor:pointer">
          <span>自動買水</span>
          <input type="checkbox" id="st-autobuy" style="width:auto" ${s.auto_buy_potion ? "checked" : ""}>
        </label>
        <div class="kv"><span class="k">買哪瓶</span>
          <select id="st-buyid" style="width:auto">${opt(potions, s.buy_potion_id || "red_potion")}</select></div>
        <div class="kv"><span class="k">補到手上有</span>
          <span><input type="number" id="st-buyupto" min="0" max="999" style="width:72px"
            value="${s.buy_potion_upto || 0}"> 瓶</span></div>
        <button class="btn primary block" id="st-save" style="margin-top:10px">儲存掛機設定</button>
      </div>`;
  },
  _wireStrategy() {
    const btn = document.querySelector("#st-save");
    if (!btn) return;
    btn.onclick = async () => {
      const g = (id) => document.querySelector(id);
      const strat = {
        ...(this._strategy || {}),
        auto_potion: g("#st-autopot").checked,
        potion_hp_pct: Math.min(0.95, Math.max(0.05, (Number(g("#st-hppct").value) || 50) / 100)),
        auto_buy_potion: g("#st-autobuy").checked,
        buy_potion_id: g("#st-buyid").value,
        buy_potion_upto: Math.max(0, Math.floor(Number(g("#st-buyupto").value) || 0)),
      };
      btn.disabled = true;
      try { await API.setHuntStrategy(S.char.id, strat); this._strategy = strat; App.toast("已儲存"); }
      catch (e) { App.toast(e.detail || "儲存失敗", true); }
      btn.disabled = false;
    };
  },
  _selectMap(mid) {
    this._mapId = mid;
    this._picked.clear();
    view().querySelectorAll("[data-map]").forEach((b) =>
      b.classList.toggle("sel", b.dataset.map === mid));
    const m = S.catalog.maps[mid];
    let html = `<div class="card"><h3>要打哪幾隻？</h3>
      <p class="muted">留空 = 自動選好打的。指定的話就照你選的打（要拚自己扛）。</p>
      <div class="list" id="monlist">`;
    for (const id of m.monster_ids) {
      const mon = S.catalog.monsters[id] || {};
      html += `<button class="btn choice" data-mon="${id}">
        ${esc(mon.name || id)}<div class="sub">Lv ${mon.level ?? "?"}</div></button>`;
    }
    html += `</div>
      <button class="btn primary block" id="btn-go" style="margin-top:12px">開始掛機</button>
      </div>`;
    document.querySelector("#monsterpick").innerHTML = html;

    view().querySelectorAll("[data-mon]").forEach((b) => {
      b.onclick = () => {
        const id = b.dataset.mon;
        if (this._picked.has(id)) this._picked.delete(id); else this._picked.add(id);
        b.classList.toggle("sel", this._picked.has(id));
      };
    });
    document.querySelector("#btn-go").onclick = () => this._go();
  },
  async _go() {
    const btn = document.querySelector("#btn-go");
    btn.disabled = true;
    try {
      await API.huntStart(this._mapId, [...this._picked]);
      App.navigate("home");
    } catch (e) { App.toast(e.detail || "開始失敗", true); btn.disabled = false; }
  },
};

// 其他分頁（build / shop / social / more / inv / gm …）由 web/js/screen-*.js
// 各自補上 Screens.xxx（在 index.html 於本檔之後載入）。

window.Screens = Screens;
window.S = S;
window.esc = esc; window.bar = bar; window.view = view;
window.Curve = Curve;
window.jobName = jobName; window.jobTier = jobTier;
window.monName = monName; window.mapName = mapName; window.itemName = itemName;
window.itemDesc = itemDesc; window.gearDesc = gearDesc; window.effectText = effectText;
window.cardDesc = cardDesc; window.SLOT_ZH = SLOT_ZH;
