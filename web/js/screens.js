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
const skillName = (id) => S.catalog?.skills?.[id]?.name || id;
const TOWN_ZH = { prontera: "普隆德拉", morroc: "摩洛克", payon: "斐揚",
  geffen: "吉芬", aldebaran: "阿爾迪巴朗" };
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
  freeze: "冰凍", sleep: "睡眠", curse: "詛咒", bleed: "流血",
  extra_hit: "追加一擊", steal_loot: "偷取額外道具" };
const CASTER_JOBS = ["mage", "wizard", "acolyte", "priest"];

// 把一個技能的效果講成白話：做什麼、吃什麼屬性。lv 給了就用該等級的數值。
function skillExplain(sk, lv) {
  lv = Math.max(1, lv || 1);
  const at = (v) => (Array.isArray(v) ? v[Math.min(lv, v.length) - 1] : v);
  const caster = CASTER_JOBS.includes(sk.job_id);
  const elem = (e) => (e.element && e.element !== "neutral" ? `（${ELEM_ZH[e.element] || e.element}屬性）` : "");
  const out = [];
  for (const e of sk.effects || []) {
    const t = e.type;
    if (t === "physical_hit" || (t === "aoe" && !caster)) {
      const hits = at(e.hits ?? 1);
      out.push(`${t === "aoe" ? "範圍" : ""}物理傷害 ${at(e.power_pct ?? 100)}%${
        hits > 1 ? ` ×${hits} 連擊` : ""}${elem(e)}，隨攻擊力（力量 STR）提升`);
      if (e.debuff === "poison") out.push("命中後使目標中毒");
    } else if (t === "magic_hit" || (t === "aoe" && caster)) {
      const hits = at(e.hits ?? 1);
      out.push(`${t === "aoe" ? "範圍" : ""}魔法傷害 ${at(e.power_pct ?? 100)}%${
        hits > 1 ? ` ×${hits}` : ""}${elem(e)}，隨魔攻（智力 INT）提升`);
    } else if (t === "heal_hp") {
      out.push(e.flat != null
        ? `回復固定 HP ${at(e.flat)}`
        : `回復 HP（魔攻的 ${at(e.matk_pct)}%，隨智力 INT 提升）`);
    } else if (t === "buff") {
      const s = Object.entries(e.stats || {})
        .map(([k, v]) => `${STAT_ZH[k] || k} +${at(v)}`).join("、");
      out.push(`增益：自身 ${s}，持續 ${e.duration_s || 0} 秒`);
    } else if (t === "debuff") {
      out.push(`減益：目標 ${STAT_ZH[e.stat] || e.stat} ${at(e.pct ?? e.amount)}%，持續 ${e.duration_s || 0} 秒`);
    } else if (t === "passive_stat") {
      out.push(`被動：${STAT_ZH[e.stat] || e.stat} +${at(e.amount)}`);
    } else if (t === "proc") {
      out.push(`被動：攻擊時 ${at(e.chance_pct)}% 機率${PROC_ZH[e.effect] || e.effect}`);
    }
  }
  return out.join("；");
}

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
    this._stopChat();
    this._worldSeen = 0;
    this._dmSeen = 0;
    this._dmOpen = null;
    this._queue = [];
    this._shown = [];
    this._lastBatch = null;
    this._hunting = null;
    this._dripMs = 0;
    this._paceBudget = 0;
    this._curMon = null;
    this._buffs = [];
    this._buffsAt = 0;
    this._sheet = await API.sheet(S.char.id).catch(() => null);
    S._sheet = this._sheet;
    this._strategy = await API.huntStrategy(S.char.id).catch(() => null);
    this._announce = await API.announcement().catch(() => null);
    let status = null;
    try { status = await API.huntStatus(); } catch (e) { if (e.status !== 409) throw e; }
    // status 這一趟可能撿到裝備，所以裝備清單在它之後才抓
    this._inv = await API.inventory(S.char.id).catch(() => null);
    if (status && status.buffs) { this._buffs = status.buffs; this._buffsAt = Date.now(); }
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
    if (status.buffs) { this._buffs = status.buffs; this._buffsAt = Date.now(); }
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
    const bb = document.querySelector("#buff-box");
    if (bb) {
      const wasOpen = bb.querySelector("details")?.open;
      bb.innerHTML = this._buffHtml();
      const d = bb.querySelector("details");
      if (d && wasOpen) d.open = true;
    }
  },

  _lootHtml(loot) {
    const held = loot || {};
    const sell = new Set((this._strategy && this._strategy.sell_item_ids) || []);
    const sellable = (id) => !S.catalog?.cards?.[id];   // 卡片以外都能賣
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

  _buffHtml() {
    const buffs = this._buffs || [];
    if (!this._hunting || !buffs.length) return "";
    const gone = (Date.now() - (this._buffsAt || Date.now())) / 1000;
    const live = buffs.map((b) => ({ ...b, left: Math.max(0, Math.round((b.remaining_s || 0) - gone)) }));
    const rows = live.map((b) => {
      const zh = STAT_ZH[b.stat] || b.stat;
      const sign = b.magnitude >= 0 ? "+" : "";
      const t = b.left > 0 ? `剩約 ${b.left} 秒` : "續投中…";
      const name = b.source ? esc(b.source) : zh;
      return `<div class="kv"><span class="k">${name}</span>` +
        `<span>${esc(zh)} ${sign}${b.magnitude}　${t}</span></div>`;
    }).join("");
    return `<details style="margin-top:4px">` +
      `<summary style="cursor:pointer" class="dim">增益中 ×${buffs.length}（點開看效果）</summary>` +
      rows + `</details>`;
  },
  _equipHtml(inv) {
    const eqs = (inv && inv.equipment) || [];
    const bySlot = {};
    for (const e of eqs) if (e.equipped_slot) bySlot[e.equipped_slot] = e;
    const worn = SLOT_ORDER.filter(([s]) => bySlot[s]).length;
    let open = false;
    try { open = localStorage.getItem("rotxt_equip_open") === "1"; } catch (_) {}
    const rows = SLOT_ORDER.map(([slot, zh]) => {
      const e = bySlot[slot];
      if (!e) {
        return `<div class="kv"><span class="k">${zh}</span>` +
          `<span class="dim">未裝備</span></div>`;
      }
      const rf = e.refine ? ` +${e.refine}` : "";
      const def = S.catalog?.equipment?.[e.equipment_id];
      const n = def?.card_slots || 0;
      const cards = (e.card_ids || []).map((c) => esc(itemName(c)));
      const tail = n
        ? ` <span class="dim">[${cards.join("、") || `空 ${n} 孔`}]</span>` : "";
      return `<div class="kv"><span class="k">${zh}</span>` +
        `<span>${esc(itemName(e.equipment_id))}${rf}${tail}</span></div>`;
    }).join("");
    const sh = S._sheet || {};
    const statBlock = sh.atk != null ? `
      <div class="kv"><span class="k">攻擊 / 魔攻</span><span>${sh.atk} / ${sh.matk}</span></div>
      <div class="kv"><span class="k">防禦 / 魔防</span><span>${sh.defense} / ${sh.mdef}</span></div>
      <div class="kv"><span class="k">命中 / 迴避</span><span>${sh.hit} / ${sh.flee}</span></div>
      <div class="kv"><span class="k">爆擊 / 攻速</span><span>${sh.crit} / ${sh.aspd}</span></div>
      <div class="kv"><span class="k">HP / SP 上限</span><span>${sh.max_hp} / ${sh.max_sp}</span></div>
      <div class="sub" style="margin:8px 0 2px">— 裝備欄 —</div>` : "";
    return `<details class="card" id="equip-box"${open ? " open" : ""}` +
      ` ontoggle="try{localStorage.setItem('rotxt_equip_open',this.open?'1':'0')}catch(e){}">` +
      `<summary style="cursor:pointer;font-weight:600">裝備與數值（${worn}/${SLOT_ORDER.length}）</summary>` +
      statBlock + rows + `</details>`;
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

    const ann = this._announce && this._announce.text;
    let html = ann
      ? `<div class="card" style="border-left:3px solid var(--accent)">
           <div class="sub" style="font-weight:600">📢 公告</div>
           <div style="white-space:pre-wrap;margin-top:4px">${esc(ann)}</div></div>`
      : "";
    html += `
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
        <div id="buff-box">${this._buffHtml()}</div>
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
    html += this._worldChatHtml();
    view().innerHTML = html;
    this._lootJson = JSON.stringify((status && status.loot) || {});
    this._wireLoot();
    this._wireWorldChat();

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

  // ---- 頻道（狀態頁可收合，預設關；世界 / 私人分頁）----
  _worldChatOpen() {
    try { return localStorage.getItem("rotxt_worldchat_open") === "1"; }
    catch (_) { return false; }
  },
  _chatTabPref() {
    try { return localStorage.getItem("rotxt_chattab") === "dm" ? "dm" : "world"; }
    catch (_) { return "world"; }
  },
  _worldChatHtml() {
    const open = this._worldChatOpen();
    const tab = this._chatTab || (this._chatTab = this._chatTabPref());
    const tb = (id, zh) =>
      `<button class="btn small ${tab === id ? "primary" : ""}" data-ctab="${id}">${zh}</button>`;
    return `<details class="card" id="world-box"${open ? " open" : ""}>` +
      `<summary style="cursor:pointer;font-weight:600">頻道</summary>` +
      `<div class="row tight" style="margin:6px 0">${tb("world", "世界")}${tb("dm", "私人")}</div>` +
      `<div id="cpane-world"${tab === "dm" ? " hidden" : ""}>` +
        `<div class="log" id="home-world-log"><span class="dim">${
          open ? "載入中…" : "展開以顯示"}</span></div>` +
        `<div class="row" style="margin-top:8px">` +
        `<input id="home-world-input" placeholder="說點什麼…" maxlength="200" style="flex:1">` +
        `<button class="btn primary" id="home-world-send">送出</button></div>` +
      `</div>` +
      `<div id="cpane-dm"${tab === "world" ? " hidden" : ""}>` +
        `<div id="dm-body"><span class="dim">${open ? "載入中…" : "展開以顯示"}</span></div>` +
        `<div class="row" style="margin-top:8px">` +
        `<input id="dm-to" placeholder="對方角色名" maxlength="24" style="flex:1">` +
        `<input id="dm-text" placeholder="密語內容" maxlength="200" style="flex:2">` +
        `<button class="btn primary" id="dm-send">送出</button></div>` +
      `</div>` +
      `</details>`;
  },
  _wireWorldChat() {
    const box = document.querySelector("#world-box");
    if (!box) return;
    box.ontoggle = () => {
      try { localStorage.setItem("rotxt_worldchat_open", box.open ? "1" : "0"); } catch (_) {}
      if (box.open) this._startChat();
      else this._stopChat();
    };
    document.querySelectorAll("#world-box [data-ctab]").forEach((b) => {
      b.onclick = () => this._switchChatTab(b.dataset.ctab);
    });
    const inp = document.querySelector("#home-world-input");
    const btn = document.querySelector("#home-world-send");
    if (inp && btn) {
      const send = async () => {
        if (this._wsending) return;            // 擋 Enter 連按重送
        const t = inp.value.trim();
        if (!t) return;
        this._wsending = true; btn.disabled = true;
        try {
          await API.chatPost("world", t);
          inp.value = "";
          await this._chatTick();
        } catch (e) { App.toast(e.detail || "送出失敗", true); }
        this._wsending = false; btn.disabled = false;
      };
      btn.onclick = send;
      inp.onkeydown = (e) => { if (e.key === "Enter") send(); };
    }
    const dto = document.querySelector("#dm-to");
    const dtx = document.querySelector("#dm-text");
    const dsend = document.querySelector("#dm-send");
    if (dto && dtx && dsend) {
      const send = async () => {
        if (this._wsending) return;
        const to = dto.value.trim(), t = dtx.value.trim();
        if (!to || !t) return;
        this._wsending = true; dsend.disabled = true;
        try {
          const m = await API.whisper(to, t);
          dtx.value = "";
          this._dmOpen = m.channel;              // 送出後直接進到這段對話
          this._dmSeen = 0;
          await this._dmTick();
        } catch (e) { App.toast(e.detail || "送出失敗", true); }
        this._wsending = false; dsend.disabled = false;
      };
      dsend.onclick = send;
      dtx.onkeydown = (e) => { if (e.key === "Enter") send(); };
    }
    const dmBody = document.querySelector("#dm-body");
    if (dmBody) {
      dmBody.onclick = (e) => {
        const back = e.target.closest("[data-dm-back]");
        if (back) { this._dmOpen = null; this._dmSeen = 0; this._dmTick(); return; }
        const row = e.target.closest("[data-dm-channel]");
        if (row) {
          this._dmOpen = row.dataset.dmChannel;
          this._dmSeen = 0;
          const to = document.querySelector("#dm-to");
          if (to) to.value = row.dataset.dmName || "";
          this._dmTick();
        }
      };
    }
    if (box.open) this._startChat();
  },
  _switchChatTab(tab) {
    if (tab === this._chatTab) return;
    this._chatTab = tab;
    try { localStorage.setItem("rotxt_chattab", tab); } catch (_) {}
    document.querySelectorAll("#world-box [data-ctab]").forEach((b) =>
      b.classList.toggle("primary", b.dataset.ctab === tab));
    const w = document.querySelector("#cpane-world");
    const d = document.querySelector("#cpane-dm");
    if (w) w.hidden = tab !== "world";
    if (d) d.hidden = tab !== "dm";
    this._startChat();
  },
  _startChat() {
    this._stopChat();
    this._chatGen = (this._chatGen || 0) + 1;
    this._worldSeen = 0;
    this._dmSeen = 0;
    this._dmOpen = null;
    const log = document.querySelector("#home-world-log");
    if (log) { log.innerHTML = "<span class='dim'>載入中…</span>"; log.dataset.empty = "1"; }
    const db = document.querySelector("#dm-body");
    if (db) db.innerHTML = "<span class='dim'>載入中…</span>";
    this._pollChannel();
    this._chatTimer = setInterval(() => this._pollChannel(), 4000);
  },
  _stopChat() {
    this._chatGen = (this._chatGen || 0) + 1;   // 作廢進行中的請求
    if (this._chatTimer) { clearInterval(this._chatTimer); this._chatTimer = null; }
    this._chatBusy = false;
  },
  _pollChannel() {
    return this._chatTab === "dm" ? this._dmTick() : this._chatTick();
  },
  _chatVisible() {
    const box = document.querySelector("#world-box");
    return S.view === "home" && box && box.open;
  },
  async _chatTick() {
    if (this._chatBusy) return;                 // 上一輪還沒回來就跳過，不重疊
    const gen = this._chatGen;
    const log = document.querySelector("#home-world-log");
    if (!this._chatVisible() || !log) return;
    this._chatBusy = true;
    try {
      const first = !this._worldSeen;
      const msgs = first
        ? await API.chatRecent("world", 25)
        : await API.chatSince("world", this._worldSeen);
      // 請求回來時若這輪已被作廢（切頁 / 重開），整批丟掉，不動畫面也不動 _worldSeen
      if (gen === this._chatGen && this._chatVisible() && this._chatTab === "world") {
        for (const m of msgs) this._worldSeen = Math.max(this._worldSeen || 0, m.id);
        const row = (m) =>
          `<div><span class="dim">${esc(m.character_name)}：</span>${esc(m.text)}</div>`;
        if (first) {
          log.innerHTML = msgs.length ? msgs.map(row).join("")
            : "<span class='dim'>還沒有訊息</span>";
          delete log.dataset.empty;
        } else if (msgs.length) {
          log.insertAdjacentHTML("beforeend", msgs.map(row).join(""));
          while (log.children.length > 80) log.removeChild(log.firstChild);
        }
        log.scrollTop = log.scrollHeight;
      }
    } catch (_) {}
    if (gen === this._chatGen) this._chatBusy = false;   // 只有當前這輪能放開鎖
  },
  async _dmTick() {
    if (this._chatBusy) return;
    const gen = this._chatGen;
    const body = document.querySelector("#dm-body");
    if (!this._chatVisible() || !body) return;
    this._chatBusy = true;
    try {
      if (this._dmOpen) {
        const first = !this._dmSeen;
        const msgs = first
          ? await API.chatRecent(this._dmOpen, 30)
          : await API.chatSince(this._dmOpen, this._dmSeen);
        if (gen === this._chatGen && this._chatVisible()
            && this._chatTab === "dm" && this._dmOpen) {
          for (const m of msgs) this._dmSeen = Math.max(this._dmSeen || 0, m.id);
          const mine = (n) => n === (S.char && S.char.name);
          const row = (m) => `<div><span class="dim">${
            mine(m.character_name) ? "我" : esc(m.character_name)}：</span>${esc(m.text)}</div>`;
          if (first) {
            body.innerHTML = `<div><a href="#" data-dm-back>← 返回私訊列表</a></div>` +
              `<div class="log" id="dm-log">${
                msgs.length ? msgs.map(row).join("") : "<span class='dim'>還沒有訊息</span>"}</div>`;
          } else if (msgs.length) {
            const dl = document.querySelector("#dm-log");
            if (dl) {
              dl.insertAdjacentHTML("beforeend", msgs.map(row).join(""));
              while (dl.children.length > 80) dl.removeChild(dl.firstChild);
            }
          }
          const dl = document.querySelector("#dm-log");
          if (dl) dl.scrollTop = dl.scrollHeight;
        }
      } else {
        const threads = await API.chatThreads();
        if (gen === this._chatGen && this._chatVisible()
            && this._chatTab === "dm" && !this._dmOpen) {
          body.innerHTML = threads.length
            ? threads.map((t) => `<div class="item" data-dm-channel="${esc(t.channel)}" ` +
                `data-dm-name="${esc(t.other_name)}" style="cursor:pointer">` +
                `<div>${esc(t.other_name)}<div class="sub">${esc(t.last_text)}</div></div></div>`).join("")
            : "<span class='dim'>還沒有私訊。下面輸入對方角色名開聊。</span>";
        }
      }
    } catch (_) {}
    if (gen === this._chatGen) this._chatBusy = false;
  },

  _logLines(events) {
    if (!events) return [];
    const out = [];
    const bbb = events.some((e) => ["attack", "skill", "kill"].includes(e.kind));
    for (const e of events) {
      if (e.kind === "attack") {
        if (!e.hit) out.push(`<span class="dim">  ${esc(e.actor)} 攻擊 ${esc(e.target)} → MISS</span>`);
        else out.push(`<span class="${e.crit ? "crit" : "hit"}">  ${esc(e.actor)} 攻擊 ${esc(e.target)} → ${e.damage}${e.crit ? " 暴擊!" : ""}</span>`);
      } else if (e.kind === "skill") {
        const dmg = e.damage ? ` → ${e.damage}` : "";
        const tgt = e.target && e.target !== e.actor ? `對 ${esc(e.target)} ` : "";
        out.push(`<span class="${e.damage ? "crit" : "hit"}">  ${esc(e.actor)} ${tgt}施放【${esc(e.skill_name)}】${dmg}</span>`);
      } else if (e.kind === "status_expired") {
        const st = (e.status || "").replace(/_mod$/, "");
        out.push(`<span class="dim">  ${esc(e.target)} 的 ${esc(STAT_ZH[st] || st)} 加成結束</span>`);
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
    this._maps = Object.values(S.catalog.maps)
      .filter((m) => bl >= (m.unlock_base_level || 1))
      .sort((a, b) => (a.unlock_base_level || 1) - (b.unlock_base_level || 1));
    this._picked = new Set();
    this._mapId = null;
    this._strategy = await API.huntStrategy(S.char.id).catch(() => ({}));

    const regions = [...new Set(this._maps.map((m) => m.town))];
    try {
      const saved = localStorage.getItem("rotxt_hunt_region");
      this._region = saved && regions.includes(saved) ? saved : "";
    } catch (_) { this._region = ""; }

    const regSel = regions.length > 1
      ? `<select id="hunt-region" style="width:100%;margin-bottom:8px">` +
        `<option value="">全部地區</option>` +
        regions.map((r) => `<option value="${r}"${this._region === r ? " selected" : ""}>${
          esc(TOWN_ZH[r] || r)}</option>`).join("") + `</select>`
      : "";

    this._search = "";
    let html = `<div class="card"><h3>選狩獵地圖</h3>${regSel}` +
      `<input id="hunt-search" placeholder="搜尋地圖或怪物名稱" style="width:100%;margin-bottom:8px">` +
      `<div class="list" id="maplist"></div></div>` +
      `<div id="monsterpick"></div>` + this._strategyCard();
    view().innerHTML = html;
    this._renderMapList();

    const ss = document.querySelector("#hunt-search");
    if (ss) ss.oninput = () => { this._search = ss.value; this._renderMapList(); };

    const rs = document.querySelector("#hunt-region");
    if (rs) rs.onchange = () => {
      this._region = rs.value;
      try { localStorage.setItem("rotxt_hunt_region", this._region); } catch (_) {}
      // 選過的地圖被篩掉了就清掉選擇，避免用被隱藏的地圖開打
      if (this._mapId && this._region
          && S.catalog.maps[this._mapId]?.town !== this._region) {
        this._mapId = null;
        this._picked.clear();
        const mp = document.querySelector("#monsterpick");
        if (mp) mp.innerHTML = "";
      }
      this._renderMapList();
    };
    this._wireStrategy();
  },

  _renderMapList() {
    const box = document.querySelector("#maplist");
    if (!box) return;
    const q = (this._search || "").trim().toLowerCase();
    let maps = this._maps.filter((m) => !this._region || m.town === this._region);
    if (q) maps = maps.filter((m) =>
      m.name.toLowerCase().includes(q)
      || m.monster_ids.some((id) => monName(id).toLowerCase().includes(q)));
    box.innerHTML = maps.map((m) => `<button class="btn choice" data-map="${m.id}">
        ${esc(m.name)}<div class="sub">解鎖 Lv ${m.unlock_base_level || 1}
        ・${m.monster_ids.map(monName).join("、")}</div></button>`).join("")
      || `<p class="muted">${q ? "沒有符合的地圖或怪物。" : "這個地區還沒有解鎖的地圖。"}</p>`;
    box.querySelectorAll("[data-map]").forEach((b) => {
      b.classList.toggle("sel", b.dataset.map === this._mapId);
      b.onclick = () => { this._selectMap(b.dataset.map); };
    });
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
        <div class="kv"><span class="k">SP 高於</span>
          <span><input type="number" id="st-skillsp" min="0" max="95" style="width:64px"
            value="${Math.round((s.skill_min_sp_pct ?? 0) * 100)}"> %　才放主動技能</span></div>
        <p class="sub">設 0 = 一律放。設高一點會留魔力、少放技能。</p>
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
        skill_min_sp_pct: Math.min(0.95, Math.max(0, (Number(g("#st-skillsp").value) || 0) / 100)),
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
    const pct = (r) => (r >= 0.1 ? Math.round(r * 100) + "%"
      : r >= 0.001 ? (r * 100).toFixed(1) + "%" : (r * 100).toFixed(2) + "%");
    let html = `<div class="card"><h3>要打哪幾隻？</h3>
      <p class="muted">留空 = 自動選好打的。指定的話就照你選的打（要拚自己扛）。點掉落物看細節。</p>
      <div class="list" id="monlist">`;
    for (const id of m.monster_ids) {
      const mon = S.catalog.monsters[id] || {};
      const drops = (mon.drops || []).map((d) =>
        `<span class="droplink" data-drop="${esc(d.item_id)}" data-owner="${id}"
          style="color:var(--accent);cursor:pointer;text-decoration:underline">${
          esc(itemName(d.item_id))} ${pct(d.rate)}</span>`).join("　");
      html += `<div class="monrow" style="margin-bottom:6px">
        <button class="btn choice" data-mon="${id}" style="width:100%">
          ${esc(mon.name || id)}<div class="sub">Lv ${mon.level ?? "?"}</div></button>
        ${drops ? `<div class="sub" style="padding:4px 6px">掉落：${drops}</div>` : ""}
        <div class="sub" id="dd-${id}" hidden style="padding:4px 6px;color:var(--muted)"></div>
      </div>`;
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
    view().querySelectorAll(".droplink").forEach((el) => {
      el.onclick = () => {
        const box = document.querySelector("#dd-" + el.dataset.owner);
        if (!box) return;
        const txt = `${itemName(el.dataset.drop)}：${
          gearDesc(el.dataset.drop) || itemDesc(el.dataset.drop) || "（無額外資料）"}`;
        if (!box.hidden && box.dataset.showing === el.dataset.drop) {
          box.hidden = true;
        } else {
          box.textContent = txt;
          box.dataset.showing = el.dataset.drop;
          box.hidden = false;
        }
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
window.skillName = skillName;
window.itemDesc = itemDesc; window.gearDesc = gearDesc; window.effectText = effectText;
window.STAT_ZH = STAT_ZH;
window.skillExplain = skillExplain;
window.cardDesc = cardDesc; window.SLOT_ZH = SLOT_ZH;
