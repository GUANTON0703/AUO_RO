// screen-more — MVP 挑戰 / 面對面交易 / GM 面板 / 登出
(() => {
  // 哪張地圖有這隻怪，圖鑑的掉落來源用來連去掛機畫面直接選那張地圖
  function monsterMapId(monsterId) {
    for (const m of Object.values(S.catalog.maps || {})) {
      if ((m.monster_ids || []).includes(monsterId)) return m.id;
    }
    return null;
  }

  function playbackDelayMs(rounds, lineCount) {
    const lines = Math.max(1, Number(lineCount) || 1);
    const floor = Math.max(7000, Math.max(0, Number(rounds) || 0) * 800);
    return Math.max(90, Math.ceil(floor / lines));
  }

  function searchCatalog(catalog, query) {
    const q = String(query ?? "").trim().toLowerCase();
    const collect = (groups) => groups.flatMap(([kind, entries]) =>
      Object.values(entries || {})
        .filter((entry) => {
          const id = String(entry.id || "");
          const name = String(entry.name || id);
          return !q || id.toLowerCase().includes(q) || name.toLowerCase().includes(q);
        })
        .map((entry) => ({ id: entry.id, name: entry.name || entry.id, kind }))
    ).sort((a, b) => a.name.localeCompare(b.name) || a.id.localeCompare(b.id));
    return {
      sources: collect([
        ["monster", catalog?.monsters],
        ["mvp", catalog?.mvps],
      ]),
      items: collect([
        ["equipment", catalog?.equipment],
        ["card", catalog?.cards],
      ]),
    };
  }

  function isValidRate(value) {
    if (value == null || String(value).trim() === "") return false;
    const rate = Number(value);
    return Number.isFinite(rate) && rate >= 0 && rate <= 1;
  }

  window.RODropRateView = { searchCatalog, isValidRate };

  window.ROFightView = { playbackDelayMs };

  // combatLogLines 回傳 {html,hp,sp}；本地備援分支回傳純字串。兩種都能顯示。
  function htmlOf(lines) {
    return (lines || []).map((l) => (l && typeof l === "object") ? l.html : l);
  }

  function fightLogLines(events) {
    // 掛機播放與 MVP 挑戰共用 combatLogLines（連續普攻併行、你打/你被打分色）
    if (typeof window.combatLogLines === "function") return window.combatLogLines(events);
    const out = [];
    for (const e of events || []) {
      if (e.kind === "attack") {
        if (!e.hit) out.push(`<span class="dim">  ${esc(e.actor)} 攻擊 ${esc(e.target)} → MISS</span>`);
        else out.push(`<span class="${e.crit ? "crit" : "hit"}">  ${esc(e.actor)} 攻擊 ${esc(e.target)} → ${e.damage}${e.crit ? " 暴擊!" : ""}</span>`);
      } else if (e.kind === "skill") {
        out.push(`<span class="hit">  ${esc(e.actor)} 使出 ${esc(e.skill_name)}${e.damage ? " → " + e.damage : ""}</span>`);
      } else if (e.kind === "heal") {
        out.push(`<span class="dim">  ${esc(e.actor)} 回復 ${e.amount}</span>`);
      } else if (e.kind === "kill") {
        out.push(`<span class="kill">${esc(e.actor)} 擊倒了 ${esc(e.target)}</span>`);
      } else if (e.kind === "fled") {
        out.push(`<span class="dim">${esc(e.actor)} 撤退了（HP ${e.hp}）</span>`);
      } else if (e.kind === "status_applied") {
        out.push(`<span class="dim">  ${esc(e.target)} 陷入 ${esc(e.status)}</span>`);
      } else if (e.kind === "challenge_result") {
        const label = { win: "勝利", loss: "戰敗", fled: "撤退" }[e.outcome] || e.outcome;
        out.push(`<span class="crit">— ${label}（${e.rounds} 回合）—</span>`);
      }
    }
    return out.slice(-60);
  }

  Screens.more = {
    async mount() {
      this._lastFight = null;
      view().innerHTML = `
        <div class="card">
          <h3>角色</h3>
          <div class="list" id="char-list"><div class="spinner">載入中…</div></div>
          <button class="btn block" id="char-new" style="margin-top:8px">+ 新增角色</button>
          <div class="row" style="margin-top:8px">
            <select id="transfer-to" style="flex:1"></select>
            <input id="transfer-amount" type="number" min="1" placeholder="金額" style="width:100px">
            <button class="btn primary" id="transfer-go">轉帳</button>
          </div>
        </div>

        <div class="card">
          <h3>圖鑑查詢</h3>
          <p class="muted">查哪個屬性、哪些裝備或卡片有加，還有哪隻怪會掉。</p>
          <div class="row" style="margin-bottom:8px">
            <select id="dex-stat" style="flex:1"></select>
            <select id="dex-slot" style="width:110px"></select>
            <select id="dex-kind" style="width:90px">
              <option value="all">全部</option>
              <option value="equipment">裝備</option>
              <option value="card">卡片</option>
            </select>
          </div>
          <div class="list" id="dex-results"></div>
        </div>

        <div class="card">
          <h3>MVP 挑戰</h3>
          <div class="list" id="mvp-list"><div class="spinner">載入中…</div></div>
        </div>

        <div class="card">
          <div class="section-title"><h3>煉製</h3><span class="sub" id="craft-level"></span></div>
          <div class="list" id="craft-list"><div class="spinner">載入中…</div></div>
        </div>

        <div class="card">
          <h3>面對面交易</h3>
          <div class="row" style="margin-bottom:8px">
            <input id="trade-to" placeholder="對方角色名稱" style="flex:1">
            <button class="btn primary" id="trade-offer">發起</button>
          </div>
          <div id="trade-pending"></div>
          <div id="trade-box"></div>
        </div>

        <div id="gm-slot"></div>

        <div class="card">
          <button class="btn block" id="btn-logout">登出</button>
        </div>`;

      document.querySelector("#btn-logout").onclick = async () => {
        try { await API.logout(); } finally { location.reload(); }
      };

      this._stopFightDrip();
      this._loadDex();
      await this._loadCharSwitcher();
      await this._loadMvp();
      await this._loadCraft();
      await this._loadTrade();
      if (S.me && S.me.is_gm) await this._loadGm();
    },

    _stopFightDrip() {
      this._fightGen = (this._fightGen || 0) + 1;   // 作廢在途的挑戰請求
      if (this._fightEnd) this._fightEnd(false);
      this._fighting = false;
    },

    // 把戰鬥訊息一則一則吐進該 MVP 下的 log；播完（或提前結束）呼叫 done()
    _playFight(lines, done, logSel) {
      this._fightLogSel = logSel;
      const log = document.querySelector(logSel);
      if (!log) { this._fighting = false; done(); return; }
      log.hidden = false;
      log.innerHTML = "";
      const step = playbackDelayMs(this._fightRounds, lines.length);
      let i = 0;

      // ended=true → 補完訊息並結算；ended=false → 只清理（畫面已切走）
      const end = (settle) => {
        if (!this._fightEnd) return;
        this._fightEnd = null;
        this._fighting = false;
        document.removeEventListener("visibilitychange", onHide);
        if (this._fightTimer) { clearTimeout(this._fightTimer); this._fightTimer = null; }
        const el = document.querySelector(this._fightLogSel);
        if (settle && el) {
          el.innerHTML = htmlOf(lines).join("\n");
          el.scrollTop = el.scrollHeight;
          done();
        }
      };
      this._fightEnd = end;
      // 分頁切走時瀏覽器凍結計時器 → 立刻補完
      const onHide = () => { if (document.hidden) end(true); };
      document.addEventListener("visibilitychange", onHide);

      const tick = () => {
        const el = document.querySelector(this._fightLogSel);
        if (!el) { end(false); return; }
        if (document.hidden) { end(true); return; }
        el.innerHTML = htmlOf(lines.slice(0, i + 1)).join("\n");
        el.scrollTop = el.scrollHeight;
        i += 1;
        if (i < lines.length) this._fightTimer = setTimeout(tick, step);
        else end(true);
      };
      tick();
    },

    // ---------- MVP ----------
    async _loadMvp() {
      const box = document.querySelector("#mvp-list");
      if (!box) return;
      try {
        const list = await API.listMvp();
        const regions = [];
        const byRegion = new Map();
        for (const m of list) {
          const key = m.region || "other";
          if (!byRegion.has(key)) {
            byRegion.set(key, { name: m.region_name || "其他", rows: [], minLv: 999 });
            regions.push(key);
          }
          const g = byRegion.get(key);
          g.rows.push(m);
          g.minLv = Math.min(g.minLv, m.level ?? 999);
        }
        regions.sort((a, b) => byRegion.get(a).minLv - byRegion.get(b).minLv);
        // 預設全部收合，只記使用者手動點開過哪些區（第一次載入時整批塞進 closed）
        if (!this._mvpRegionClosed) this._mvpRegionClosed = new Set(regions);
        const closed = this._mvpRegionClosed;
        const rowHtml = (m) => {
          const cd = !m.available;
          const secs = m.seconds_remaining || 0;
          const ago = (s) => s < 60 ? `${s} 秒前`
            : s < 3600 ? `${Math.round(s / 60)} 分前` : `${Math.round(s / 3600)} 小時前`;
          const wait = cd
            ? `${Math.ceil(secs / 60)} 分後復活${m.last_killer
                ? `（${ago(m.killed_ago || 0)}被 ${esc(m.last_killer)} 擊殺）` : ""}`
            : "可挑戰";
          // MVP 挑戰掉落率是內容值的 3 倍（上限 100%），顯示實際機率
          const pct = (r) => {
            const e = Math.min(1, r * 3);
            return e >= 0.1 ? Math.round(e * 100) + "%"
              : e >= 0.001 ? (e * 100).toFixed(1) + "%" : (e * 100).toFixed(2) + "%";
          };
          const drops = (m.drops || [])
            .sort((a, b) => (a.item_id === `${m.id}_card` ? -1 : 0))
            .map((d) => `<span class="droplink" data-drop="${esc(d.item_id)}" data-owner="mvp-${esc(m.id)}"
              style="color:var(--accent);cursor:pointer;text-decoration:underline">${
              esc(d.name)} ${pct(d.rate)}</span>`).join("　");
          const dropLine = drops
            ? `<div class="sub" style="color:var(--muted)">掉落：${drops}</div>
               <div class="sub" id="dd-mvp-${esc(m.id)}" hidden style="color:var(--muted)"></div>` : "";
          return `<div class="mvp-row">
            <div class="item${cd ? " mvp-dead" : ""}" style="align-items:flex-start"><div>${esc(m.name)}
              <div class="sub">Lv ${m.level ?? "?"}・${esc(m.home_map_name || "")}・${wait}</div>
              ${dropLine}</div>
              <button class="btn small" data-mvp="${esc(m.id)}"${cd ? " disabled" : ""}>挑戰</button></div>
            <div class="log mvp-fight" id="fight-${esc(m.id)}" hidden></div>
            <div id="result-${esc(m.id)}"></div>
          </div>`;
        };
        box.innerHTML = regions.map((key) => {
          const g = byRegion.get(key);
          const isClosed = closed.has(key);
          const rows = g.rows.slice().sort((a, b) => (a.level ?? 0) - (b.level ?? 0));
          return `<div class="mvp-region-hd" data-region="${esc(key)}">
              <span class="arw">${isClosed ? "▸" : "▾"}</span> ${esc(g.name)}
              <span class="muted">（${rows.length}・Lv ${g.minLv}+）</span></div>
            <div class="mvp-region-body"${isClosed ? " hidden" : ""}>${rows.map(rowHtml).join("")}</div>`;
        }).join("") || "<p class='muted'>沒有 MVP</p>";
        box.querySelectorAll(".mvp-region-hd").forEach((hd) => {
          hd.onclick = () => {
            const k = hd.dataset.region;
            if (closed.has(k)) closed.delete(k); else closed.add(k);
            const body = hd.nextElementSibling;
            if (body) body.hidden = closed.has(k);
            const arw = hd.querySelector(".arw");
            if (arw) arw.textContent = closed.has(k) ? "▸" : "▾";
          };
        });
        box.querySelectorAll(".droplink").forEach((el) => {
          el.onclick = () => {
            const dd = box.querySelector("#dd-" + el.dataset.owner);
            if (!dd) return;
            const txt = `${itemName(el.dataset.drop)}：${
              gearDesc(el.dataset.drop) || itemDesc(el.dataset.drop) || "（無額外資料）"}`;
            if (!dd.hidden && dd.dataset.showing === el.dataset.drop) {
              dd.hidden = true;
            } else {
              dd.textContent = txt;
              dd.dataset.showing = el.dataset.drop;
              dd.hidden = false;
            }
          };
        });
        box.querySelectorAll("[data-mvp]").forEach((b) => {
          b.onclick = () => this._challenge(b.dataset.mvp, b);
        });
        // 剛打完的那場，把記錄跟結果貼回該 MVP 下面
        const lf = this._lastFight;
        if (lf) {
          const flog = box.querySelector(`#fight-${lf.id}`);
          const fres = box.querySelector(`#result-${lf.id}`);
          if (flog) { flog.hidden = false; flog.innerHTML = htmlOf(lf.lines).join("\n"); }
          if (fres) fres.innerHTML = lf.resultHtml;
        }
      } catch (e) { box.innerHTML = `<p class="muted">${esc(e.detail || "載入失敗")}</p>`; }
    },

    async _challenge(id, btn) {
      if (this._fighting) return;
      if (!confirm("確定挑戰這隻 MVP？戰敗會損失少量經驗。")) return;
      this._fighting = true;
      const gen = (this._fightGen || 0);
      document.querySelectorAll("#mvp-list [data-mvp]").forEach((b) => { b.disabled = true; });
      const res = document.querySelector(`#result-${id}`);
      if (res) res.innerHTML = "";
      let r;
      try {
        r = await API.challengeMvp(id);
      } catch (e) {
        if (gen !== (this._fightGen || 0)) return;
        App.toast(e.detail || "挑戰失敗", true);
        this._fighting = false;
        await this._loadMvp();
        return;
      }
      if (gen !== (this._fightGen || 0)) return;   // 已離開 More 畫面，丟棄結果
      this._fightRounds = r.rounds || 0;
      const lines = fightLogLines(r.events);
      this._playFight(lines, async () => {
        const label = { win: "勝利", loss: "戰敗", fled: "撤退" }[r.outcome] || r.outcome;
        const cls = r.outcome === "win" ? "good" : r.outcome === "loss" ? "bad" : "warn";
        let line = `<span class="pill ${cls}">${label}</span> `;
        if (r.outcome === "win") {
          line += `經驗 +${r.base_exp}/${r.job_exp}　Zeny +${r.zeny}`;
          const d = Object.entries(r.drops || {});
          if (d.length) line += `<br>掉落：${d.map(([k, v]) => `${esc(itemName(k))}×${v}`).join("、")}`;
        } else if (r.outcome === "loss") {
          line += `損失經驗 -${r.exp_penalty}`;
        } else {
          line += `全身而退，無損失`;
        }
        const resultHtml = `<p style="margin-top:8px">${line}</p>`;
        const box = document.querySelector(`#result-${id}`);
        if (box) box.innerHTML = resultHtml;
        // 記著這場結果，_loadMvp 重繪清單後再貼回同一隻 MVP 下面
        this._lastFight = { id, lines, resultHtml };
        await App.refreshChar();
        await this._loadMvp();
      }, `#fight-${id}`);
    },

    // ---------- 煉製 ----------
    async _loadCraft() {
      const box = document.querySelector("#craft-list");
      if (!box) return;
      try {
        const data = await API.listCraft();
        const lv = document.querySelector("#craft-level");
        if (lv) {
          lv.textContent = data.craft_exp_next
            ? `Lv ${data.craft_level}（${data.craft_exp} / ${data.craft_exp_next}）`
            : `Lv ${data.craft_level}（滿級）`;
        }
        box.innerHTML = (data.recipes || []).map((r) => {
          const mats = r.materials.map((m) => {
            const short = m.have < m.need;
            return `<span${short ? ` style="color:var(--bad)"` : ""}>${esc(m.name)} ${m.have}/${m.need}</span>`;
          }).join("　");
          const canOne = r.materials.every((m) => m.have >= m.need);
          const canFive = r.materials.every((m) => m.have >= m.need * 5);
          const canTen = r.materials.every((m) => m.have >= m.need * 10);
          return `<div class="item" style="align-items:flex-start"><div>
              <div>${esc(r.name)}<span class="pill" style="margin-left:6px">成功率 ${r.success_pct}%</span></div>
              <div class="sub">產出：${esc(r.result_item_name)} ×${r.result_qty}　需製作等級 ${r.required_craft_level}${
                r.zeny_cost ? `　${r.zeny_cost}z/次` : ""}</div>
              <div class="sub">熟練度：做過 ${r.mastery_attempts} 次（+${r.mastery_bonus_pct}%）${
                r.mastery_next ? `，再 ${r.mastery_next} 次加一階` : "・已練到頂"}</div>
              <div class="sub">${mats}</div>
              <div id="craft-result-${esc(r.id)}"></div>
            </div>
            <div class="row tight" style="flex-wrap:wrap">
              <button class="btn small" data-craft="${esc(r.id)}" data-times="1"${canOne ? "" : " disabled"}>做 1</button>
              <button class="btn small" data-craft="${esc(r.id)}" data-times="5"${canFive ? "" : " disabled"}>做 5</button>
              <button class="btn small" data-craft="${esc(r.id)}" data-times="10"${canTen ? "" : " disabled"}>做 10</button>
            </div></div>`;
        }).join("") || "<p class='muted'>還沒有配方</p>";
        box.querySelectorAll("[data-craft]").forEach((b) => {
          b.onclick = () => this._doCraft(b.dataset.craft, Number(b.dataset.times));
        });
      } catch (e) { box.innerHTML = `<p class="muted">${esc(e.detail || "載入失敗")}</p>`; }
    },
    async _doCraft(recipeId, times) {
      document.querySelectorAll(`[data-craft="${recipeId}"]`).forEach((b) => { b.disabled = true; });
      try {
        const r = await API.craft(recipeId, times);
        const box = document.querySelector(`#craft-result-${recipeId}`);
        const line = `製作 ${r.attempts} 次：成功 ${r.successes}${
          r.great_successes ? `（大成功 ${r.great_successes}）` : ""}、失敗 ${r.fails}，` +
          `拿到 ${esc(itemName(r.result_item))} ×${r.produced}`;
        if (box) box.innerHTML = `<p class="sub">${line}</p>`;
        App.toast(line);
      } catch (e) { App.toast(e.detail || "製作失敗", true); }
      await this._loadCraft();
    },

    // ---------- 圖鑑查詢 ----------
    _loadDex() {
      const DEX_STATS = [
        ["str", "力量"], ["agi", "敏捷"], ["vit", "體質"], ["int", "智力"],
        ["dex", "靈巧"], ["luk", "幸運"],
        ["atk", "攻擊"], ["matk", "魔攻"], ["defense", "防禦"], ["mdef", "魔防"],
        ["hit", "命中"], ["flee", "迴避"], ["crit", "爆擊"], ["aspd", "攻速"],
        ["max_hp", "HP上限"], ["max_sp", "SP上限"],
      ];
      const statSel = document.querySelector("#dex-stat");
      const slotSel = document.querySelector("#dex-slot");
      const kindSel = document.querySelector("#dex-kind");
      if (!statSel) return;
      statSel.innerHTML = DEX_STATS.map(([k, zh]) =>
        `<option value="${k}"${k === this._dexStat ? " selected" : ""}>${esc(zh)}</option>`).join("");
      this._dexStat = statSel.value;
      const SLOTS = [["", "全部部位"], ["weapon", "武器"], ["offhand", "副手"], ["head", "頭部"],
        ["armor", "鎧甲"], ["garment", "披肩"], ["shoes", "鞋子"], ["accessory", "飾品"]];
      slotSel.innerHTML = SLOTS.map(([v, zh]) =>
        `<option value="${v}"${v === (this._dexSlot || "") ? " selected" : ""}>${esc(zh)}</option>`).join("");
      statSel.onchange = () => { this._dexStat = statSel.value; this._renderDex(); };
      slotSel.onchange = () => { this._dexSlot = slotSel.value; this._renderDex(); };
      kindSel.onchange = () => { this._dexKind = kindSel.value; this._renderDex(); };
      this._renderDex();
    },

    _dexStatHit(effects, stat) {
      for (const e of effects || []) {
        if (e.stat !== stat) continue;
        if (e.type === "flat_stat") return { amount: e.amount, pct: false };
        if (e.type === "percent_stat") return { amount: e.pct, pct: true };
      }
      return null;
    },

    _dexDropSources(itemId) {
      const out = [];
      // MVP 沒有對應的「去掛機」——挑戰是另一套流程，掉落來源不給地圖連結
      const scan = (coll, isMvp) => Object.values(coll || {}).forEach((m) => {
        for (const d of m.drops || []) {
          if (d.item_id === itemId) out.push({ name: m.name, rate: d.rate,
            mapId: isMvp ? null : monsterMapId(m.id) });
        }
      });
      scan(S.catalog.monsters, false);
      scan(S.catalog.mvps, true);
      return out.sort((a, b) => b.rate - a.rate);
    },

    _renderDex() {
      const box = document.querySelector("#dex-results");
      if (!box) return;
      const stat = this._dexStat;
      const slot = this._dexSlot || "";
      const kind = this._dexKind || "all";
      const pct = (r) => (r >= 0.1 ? Math.round(r * 100) + "%"
        : r >= 0.001 ? (r * 100).toFixed(1) + "%" : (r * 100).toFixed(2) + "%");
      const rows = [];

      if (kind !== "card") {
        for (const eq of Object.values(S.catalog.equipment || {})) {
          if (slot && eq.slot !== slot) continue;
          let amt = eq.stats && eq.stats[stat];
          let isPct = false;
          if (amt == null) {
            const hit = this._dexStatHit(eq.effects, stat);
            if (hit) { amt = hit.amount; isPct = hit.pct; }
          }
          if (amt == null) continue;
          rows.push({ srcKind: "裝備", name: eq.name, slot: eq.slot, amt, isPct,
            buy: eq.npc_buy, drops: this._dexDropSources(eq.id) });
        }
      }
      if (kind !== "equipment") {
        for (const c of Object.values(S.catalog.cards || {})) {
          if (slot && c.slot !== slot) continue;
          const hit = this._dexStatHit(c.effects, stat);
          if (!hit) continue;
          rows.push({ srcKind: "卡片", name: c.name, slot: c.slot, amt: hit.amount, isPct: hit.pct,
            buy: null, drops: this._dexDropSources(c.id) });
        }
      }
      rows.sort((a, b) => b.amt - a.amt);

      box.innerHTML = rows.length ? rows.map((r) => {
        const amtTxt = `${r.amt >= 0 ? "+" : ""}${r.amt}${r.isPct ? "%" : ""}`;
        const where = r.drops.length
          ? r.drops.slice(0, 4).map((d) => {
              const label = `${esc(d.name)} ${pct(d.rate)}`;
              return d.mapId
                ? `<a href="#" class="dex-map-link" data-map="${d.mapId}">${label}</a>`
                : label;
            }).join("、")
          : (r.buy ? `商店買（${r.buy}z）` : "取得方式不明");
        return `<div class="item">
          <div>${esc(r.name)}<span class="pill" style="margin-left:6px">${r.srcKind}</span>
            <div class="sub">${SLOT_ZH[r.slot] || r.slot}　${amtTxt}</div>
            <div class="sub">來源：${where}</div>
          </div>
        </div>`;
      }).join("") : `<p class="muted">沒有裝備或卡片有加這個屬性。</p>`;
      box.querySelectorAll(".dex-map-link").forEach((a) => {
        a.onclick = (ev) => {
          ev.preventDefault();
          S._pendingHuntMap = a.dataset.map;
          App.navigate("hunt");
        };
      });
    },

    // ---------- 角色切換 / 轉帳 ----------
    async _loadCharSwitcher() {
      let chars;
      try { chars = await API.listCharacters(); }
      catch (e) { App.toast(e.detail || "角色清單載入失敗", true); return; }

      const list = document.querySelector("#char-list");
      if (list) {
        list.innerHTML = chars.map((c) => `
          <div class="item">
            <div>${esc(c.name)}${c.is_active ? `<span class="pill" style="margin-left:6px">目前</span>` : ""}
              <div class="sub">Lv ${c.base_level}　Zeny ${c.zeny}</div></div>
            ${c.is_active ? "" : `<button class="btn small" data-switch-char="${c.id}">切換</button>`}
          </div>`).join("");
        list.querySelectorAll("[data-switch-char]").forEach((b) => {
          b.onclick = async () => {
            b.disabled = true;
            try { await App.switchCharacter(Number(b.dataset.switchChar)); }
            catch (e) { App.toast(e.detail || "切換失敗", true); b.disabled = false; }
          };
        });
      }

      const newBtn = document.querySelector("#char-new");
      if (newBtn) {
        newBtn.hidden = chars.length >= 3;
        newBtn.onclick = async () => {
          const name = prompt("新角色的名字？");
          if (!name || !name.trim()) return;
          newBtn.disabled = true;
          try { await App.createCharacter(name.trim()); }
          catch (e) { App.toast(e.detail || "建立失敗", true); newBtn.disabled = false; }
        };
      }

      const toSel = document.querySelector("#transfer-to");
      if (toSel) {
        const others = chars.filter((c) => !c.is_active);
        toSel.innerHTML = others.length
          ? others.map((c) => `<option value="${c.id}">${esc(c.name)}</option>`).join("")
          : `<option value="">（沒有別的角色）</option>`;
      }
      const goBtn = document.querySelector("#transfer-go");
      if (goBtn) goBtn.onclick = async () => {
        const toId = Number(toSel?.value || 0);
        const amount = Math.floor(Number(document.querySelector("#transfer-amount").value) || 0);
        if (!toId) { App.toast("沒有可以轉的角色", true); return; }
        if (amount <= 0) { App.toast("金額要大於 0", true); return; }
        goBtn.disabled = true;
        try {
          await API.transferZeny(toId, amount);
          App.toast(`轉了 ${amount}z`);
          await App.refreshChar();
          await this._loadCharSwitcher();
        } catch (e) { App.toast(e.detail || "轉帳失敗", true); }
        goBtn.disabled = false;
      };
    },

    // ---------- 交易 ----------
    async _loadTrade() {
      document.querySelector("#trade-offer").onclick = async () => {
        const to = document.querySelector("#trade-to").value.trim();
        if (!to) return;
        try {
          const r = await API.tradeOffer(to);
          this._openTrade(r.trade_id ?? r.id, "from");
        } catch (e) { App.toast(e.detail || "發起失敗", true); }
      };

      // 之前開著的交易（換分頁 / reload 後還能回去確認或取消）
      if (!this._tid) {
        const saved = (localStorage.getItem("rotxt_trade") || "").split(":");
        if (saved[0]) {
          try {
            const t = await API.tradeGet(Number(saved[0]));
            if (t && t.status === "open") { this._openTrade(Number(saved[0]), saved[1] || "from"); return; }
          } catch (_) {}
          localStorage.removeItem("rotxt_trade");
        }
      }

      const pend = document.querySelector("#trade-pending");
      try {
        const rows = await API.tradePending();
        pend.innerHTML = rows.length
          ? `<p class="muted">待處理交易</p>` + rows.map((t) =>
              `<div class="item"><div>${esc(t.from_name || "？")} 想跟你交易</div>
                <button class="btn small" data-trade="${t.id}">開啟</button></div>`).join("")
          : "";
        pend.querySelectorAll("[data-trade]").forEach((b) => {
          b.onclick = () => this._openTrade(Number(b.dataset.trade), "to");
        });
      } catch (_) { pend.innerHTML = ""; }
    },

    async _openTrade(tid, side) {
      this._tid = tid;
      this._side = side;
      localStorage.setItem("rotxt_trade", tid + ":" + side);
      await this._renderTrade();
    },

    _closeTrade() {
      this._tid = null;
      localStorage.removeItem("rotxt_trade");
    },

    async _renderTrade() {
      const box = document.querySelector("#trade-box");
      if (!this._tid) { box.innerHTML = ""; return; }
      let t;
      try { t = await API.tradeGet(this._tid); }
      catch (e) { box.innerHTML = `<p class="muted">${esc(e.detail || "交易不存在")}</p>`; return; }
      const mine = (t.items || []).filter((i) => i.side === this._side);
      const theirs = (t.items || []).filter((i) => i.side !== this._side);
      // 桌上的道具/卡片(共用 item_id 欄位) 或裝備，都秀出名稱＋細節（卡片/裝備效果、精煉）
      const anyItemDesc = (id) => itemDesc(id) || cardDesc(id);
      const fmtLine = (i) => {
        if (i.item_id) {
          const d = anyItemDesc(i.item_id);
          return `<div class="sub">${esc(itemName(i.item_id))} ×${i.qty}${d ? `　${esc(d)}` : ""}</div>`;
        }
        const eqId = i.catalog_equipment_id;
        if (!eqId) return `<div class="sub">裝備（已轉移，細節看不到了）</div>`;
        const cardsTxt = (i.card_ids || []).map((c) => {
          const fx = cardDesc(c);
          return `${itemName(c)}${fx ? `（${fx}）` : ""}`;
        }).join("、");
        const desc = gearDesc(eqId, i.refine || 0);
        return `<div class="sub">${esc(itemName(eqId))}${i.refine ? ` +${i.refine}` : ""}${
          desc ? `　${esc(desc)}` : ""}${cardsTxt ? `　卡：${esc(cardsTxt)}` : ""}</div>`;
      };
      const fmt = (arr) => arr.length ? arr.map(fmtLine).join("") : `<div class="sub muted">（空）</div>`;
      const done = t.status !== "open";
      let inv = { items: {}, equipment: [] };
      if (!done) { try { inv = await API.inventory(S.char.id); } catch (_) {} }

      // 裝備分職業篩選，跟背包那邊同一套邏輯：全職業通用件不受篩選影響
      const tradeEq = (inv.equipment || []).filter((e) => !e.equipped_slot);
      const tradeJobsPresent = [...new Set(tradeEq
        .flatMap((e) => S.catalog?.equipment?.[e.equipment_id]?.job_ids || []))];
      if (this._tradeEqJob && !tradeJobsPresent.includes(this._tradeEqJob)) this._tradeEqJob = "";
      const tradeJobOptions = [`<option value="">全部職業</option>`].concat(
        tradeJobsPresent.map((j) => `<option value="${j}"${this._tradeEqJob === j ? " selected" : ""}>${esc(jobName(j))}</option>`),
      ).join("");
      const eqMatchesJob = (e) => {
        if (!this._tradeEqJob) return true;
        const jobIds = S.catalog?.equipment?.[e.equipment_id]?.job_ids || [];
        return jobIds.length === 0 || jobIds.includes(this._tradeEqJob);
      };

      const itemRows = Object.entries(inv.items || {}).map(([id, qty]) => `
        <div class="item">
          <div>${esc(itemName(id))} ×${qty}<div class="sub">${esc(anyItemDesc(id) || "")}</div></div>
          <button class="btn small" data-put-item="${esc(id)}">放上</button>
        </div>`).join("");
      const eqRows = tradeEq.filter(eqMatchesJob).map((e) => `
        <div class="item">
          <div>${esc(itemName(e.equipment_id))}${e.refine ? ` +${e.refine}` : ""}
            <div class="sub">${esc(gearDesc(e.equipment_id, e.refine || 0) || "")}</div></div>
          <button class="btn small" data-put-eq="${e.id}">放上</button>
        </div>`).join("");

      box.innerHTML = `
        <div class="card" style="margin-top:10px">
          <div class="kv"><span class="k">交易 #${t.id}</span><span class="pill">${esc(t.status)}</span></div>
          <div class="kv"><span class="k">對象</span><span>${esc(
            this._side === "from" ? (t.to_name || "？") : (t.from_name || "？"))}</span></div>
          <div class="k" style="margin-top:6px">我方放上</div>${fmt(mine)}
          <div class="k" style="margin-top:6px">對方放上</div>${fmt(theirs)}
          ${done ? "" : `
          <p class="muted" style="margin-top:8px">點「放上」放入（道具會問數量）</p>
          <div class="list">${itemRows || "<p class='muted'>沒有道具</p>"}</div>
          <div class="row tight" style="margin-top:8px"><select id="trade-eq-job" style="flex:1">${tradeJobOptions}</select></div>
          <div class="list">${eqRows || "<p class='muted'>沒有可交易裝備</p>"}</div>`}
          <div class="row" style="margin-top:10px">
            <button class="btn primary" id="trade-confirm"${done ? " disabled" : ""}>確認</button>
            <button class="btn" id="trade-cancel"${done ? " disabled" : ""}>取消</button>
            <button class="btn ghost" id="trade-refresh">重新整理</button>
          </div>
        </div>`;

      const tradeEqJobSel = box.querySelector("#trade-eq-job");
      if (tradeEqJobSel) tradeEqJobSel.onchange = () => { this._tradeEqJob = tradeEqJobSel.value; this._renderTrade(); };

      box.querySelectorAll("[data-put-item]").forEach((b) => {
        b.onclick = async () => {
          const qty = Number(prompt("放入數量", "1")) || 0;
          if (qty < 1) return;
          try { await API.tradePut(this._tid, { item_id: b.dataset.putItem, qty }); await this._renderTrade(); }
          catch (e) { App.toast(e.detail || "放入失敗", true); }
        };
      });
      box.querySelectorAll("[data-put-eq]").forEach((b) => {
        b.onclick = async () => {
          try { await API.tradePut(this._tid, { equipment_instance_id: Number(b.dataset.putEq) }); await this._renderTrade(); }
          catch (e) { App.toast(e.detail || "放入失敗", true); }
        };
      });
      document.querySelector("#trade-confirm").onclick = async () => {
        try {
          const r = await API.tradeConfirm(this._tid);
          App.toast(r.status === "done" ? "交易完成" : "已確認，等待對方");
          if (r.status === "done") { this._closeTrade(); await App.refreshChar(); await this._loadTrade(); }
          await this._renderTrade();
        } catch (e) { App.toast(e.detail || "確認失敗", true); }
      };
      document.querySelector("#trade-cancel").onclick = async () => {
        try { await API.tradeCancel(this._tid); App.toast("已取消"); this._closeTrade(); box.innerHTML = ""; await this._loadTrade(); }
        catch (e) { App.toast(e.detail || "取消失敗", true); }
      };
      document.querySelector("#trade-refresh").onclick = () => this._renderTrade();
    },

    // ---------- GM ----------
    async _loadGm() {
      const slot = document.querySelector("#gm-slot");
      slot.innerHTML = `<div class="card"><h3>GM 面板</h3>
        <div id="gm-settings"><div class="spinner">載入中…</div></div>
        <div class="section-title" style="margin-top:10px"><span class="k">倍率</span></div>
        <div class="row tight">
          <input id="gm-exp" type="number" step="0.1" placeholder="經驗" style="flex:1">
          <input id="gm-drop" type="number" step="0.1" placeholder="掉寶" style="flex:1">
          <input id="gm-zenym" type="number" step="0.1" placeholder="金錢" style="flex:1">
          <button class="btn small" id="gm-mult">套用</button>
        </div>
        <div class="section-title" style="margin-top:10px"><span class="k">掛機</span></div>
        <div class="row">
          <input id="gm-floor" type="number" step="1" placeholder="結算地板秒" style="flex:1">
          <input id="gm-wr" type="number" step="0.05" placeholder="勝率門檻" style="flex:1">
          <button class="btn small" id="gm-hunt">套用</button>
        </div>
        <div class="section-title" style="margin-top:10px"><span class="k">操作對象</span></div>
        <div class="row">
          <input id="gm-target-search" placeholder="搜尋角色名 / 帳號（留空 = 我自己）" style="flex:1">
        </div>
        <div id="gm-target-results" class="list" style="margin-top:4px"></div>
        <div class="kv" style="margin-top:4px"><span class="k">目前對象</span>
          <span id="gm-target-cur" class="pill">${esc(S.char.name)}（我自己）</span></div>
        <div class="row">
          <input id="gm-zeny" type="number" placeholder="給 Zeny（可負）" style="flex:1">
          <button class="btn small" id="gm-money">給錢</button>
        </div>
        <div class="row" style="margin-top:6px">
          <input id="gm-be" type="number" placeholder="base_exp" style="flex:1">
          <input id="gm-je" type="number" placeholder="job_exp" style="flex:1">
          <button class="btn small" id="gm-xp">設經驗</button>
        </div>
        <div class="section-title" style="margin-top:10px"><span class="k">給物品（進倉庫，不是背包）</span></div>
        <div class="row">
          <input id="gm-item-search" placeholder="搜尋道具 / 裝備 / 卡片" style="flex:1">
        </div>
        <div class="row" style="margin-top:6px">
          <select id="gm-item-select" style="flex:1"></select>
          <input id="gm-item-qty" type="number" min="1" value="1" placeholder="數量" style="width:80px">
          <input id="gm-item-refine" type="number" min="0" max="10" value="0" placeholder="精煉" style="width:70px">
          <button class="btn small" id="gm-item-give">給</button>
        </div>
        <div class="section-title" style="margin-top:10px"><span class="k">公告</span></div>
        <div class="row">
          <input id="gm-ann" placeholder="留空 = 清除公告" maxlength="500" style="flex:1">
          <button class="btn small" id="gm-ann-save">發布</button>
        </div>
        <div class="section-title" style="margin-top:10px"><span class="k">裝備 / 卡片掉落率</span></div>
        <div class="row">
          <input id="gm-drop-source-search" placeholder="搜尋怪物 / Boss" style="flex:1">
          <input id="gm-drop-item-search" placeholder="搜尋裝備 / 卡片" style="flex:1">
        </div>
        <div class="row" style="margin-top:6px">
          <select id="gm-drop-source" style="flex:1"></select>
          <select id="gm-drop-item" style="flex:1"></select>
        </div>
        <div id="gm-drop-rate-status" style="margin-top:6px"><p class="muted">選擇來源與物品後載入有效率</p></div>
        <div class="row" style="margin-top:6px">
          <input id="gm-drop-rate" type="number" min="0" max="1" step="0.0001" placeholder="有效率 0..1" style="flex:1">
          <button class="btn small" id="gm-drop-save">設定</button>
          <button class="btn small ghost" id="gm-drop-clear">清除覆寫</button>
        </div>
        <div class="section-title" style="margin-top:10px"><span class="k">線上玩家</span>
          <button class="btn small ghost" id="gm-online-refresh">刷新</button></div>
        <div class="list" id="gm-online"></div>
      </div>`;

      const showSettings = async () => {
        try {
          const s = await API.adminSettings();
          document.querySelector("#gm-settings").innerHTML = `
            <div class="kv"><span class="k">經驗倍率</span><span>${s.experience_multiplier}</span></div>
            <div class="kv"><span class="k">掉寶倍率</span><span>${s.drop_multiplier}</span></div>
            <div class="kv"><span class="k">金錢倍率</span><span>${s.zeny_multiplier}</span></div>
            <div class="kv"><span class="k">結算地板秒</span><span>${s.settle_floor_seconds}</span></div>
            <div class="kv"><span class="k">勝率門檻</span><span>${s.huntable_win_rate}</span></div>`;
          document.querySelector("#gm-exp").value = s.experience_multiplier;
          document.querySelector("#gm-drop").value = s.drop_multiplier;
          document.querySelector("#gm-zenym").value = s.zeny_multiplier;
          document.querySelector("#gm-floor").value = s.settle_floor_seconds;
          document.querySelector("#gm-wr").value = s.huntable_win_rate;
        } catch (e) { document.querySelector("#gm-settings").innerHTML = `<p class="muted">${esc(e.detail || "載入失敗")}</p>`; }
      };
      const showOnline = async () => {
        try {
          const rows = await API.adminOnlinePlayers();
          document.querySelector("#gm-online").innerHTML = rows.map((p) =>
            `<div class="item"><div>${esc(p.name || p.username)}
              <div class="sub">${esc(p.username)}・B${p.base_level ?? "?"}/J${p.job_level ?? "?"}</div></div>
              <span>${p.zeny ?? 0}z</span></div>`).join("") || "<p class='muted'>沒有線上玩家</p>";
        } catch (_) {}
      };

      document.querySelector("#gm-mult").onclick = async () => {
        try {
          await API.adminSetMultipliers(
            Number(document.querySelector("#gm-exp").value),
            Number(document.querySelector("#gm-drop").value),
            Number(document.querySelector("#gm-zenym").value) || 1);
          App.toast("已套用"); showSettings();
        } catch (e) { App.toast(e.detail || "失敗", true); }
      };
      document.querySelector("#gm-hunt").onclick = async () => {
        try {
          await API.adminSetHunt(Number(document.querySelector("#gm-floor").value), Number(document.querySelector("#gm-wr").value));
          App.toast("已套用"); showSettings();
        } catch (e) { App.toast(e.detail || "失敗", true); }
      };
      // 操作對象：預設自己，搜到人選一個就換過去，之後給錢/給經驗/給物品都對這個人
      this._gmTargetId = S.char.id;
      const targetId = () => this._gmTargetId || S.char.id;
      const gmTargetSearch = document.querySelector("#gm-target-search");
      const gmTargetResults = document.querySelector("#gm-target-results");
      const gmTargetCur = document.querySelector("#gm-target-cur");
      let gmTargetReq = 0;
      gmTargetSearch.oninput = async () => {
        const q = gmTargetSearch.value.trim();
        const gen = ++gmTargetReq;
        if (!q) { gmTargetResults.innerHTML = ""; return; }
        let rows;
        try { rows = await API.adminSearchCharacters(q); } catch (_) { return; }
        if (gen !== gmTargetReq) return;   // 打字太快，舊的搜尋結果別蓋掉新的
        gmTargetResults.innerHTML = rows.length ? rows.map((r) => `
          <div class="item">
            <div>${esc(r.name)}<div class="sub">${esc(r.username)}・B${r.base_level}/J${r.job_level}・${r.zeny}z</div></div>
            <button class="btn small" data-pick-target="${r.character_id}" data-name="${esc(r.name)}">選這個</button>
          </div>`).join("") : `<p class="muted">沒有符合的角色</p>`;
        gmTargetResults.querySelectorAll("[data-pick-target]").forEach((b) => {
          b.onclick = () => {
            this._gmTargetId = Number(b.dataset.pickTarget);
            gmTargetCur.textContent = b.dataset.name;
            gmTargetResults.innerHTML = ""; gmTargetSearch.value = "";
          };
        });
      };
      document.querySelector("#gm-money").onclick = async () => {
        try {
          await API.adminMoney(targetId(), Number(document.querySelector("#gm-zeny").value) || 0);
          App.toast("已給錢"); if (targetId() === S.char.id) await App.refreshChar();
        } catch (e) { App.toast(e.detail || "失敗", true); }
      };
      document.querySelector("#gm-xp").onclick = async () => {
        try {
          await API.adminExperience(targetId(), Number(document.querySelector("#gm-be").value) || 0, Number(document.querySelector("#gm-je").value) || 0);
          App.toast("已設經驗"); if (targetId() === S.char.id) await App.refreshChar();
        } catch (e) { App.toast(e.detail || "失敗", true); }
      };

      document.querySelector("#gm-online-refresh").onclick = showOnline;
      document.querySelector("#gm-ann-save").onclick = async () => {
        try {
          const r = await API.adminSetAnnouncement(document.querySelector("#gm-ann").value);
          App.toast(r.text ? "公告已發布" : "公告已清除");
        } catch (e) { App.toast(e.detail || "失敗", true); }
      };

      const dropView = window.RODropRateView;
      const dropSourceSearch = document.querySelector("#gm-drop-source-search");
      const dropItemSearch = document.querySelector("#gm-drop-item-search");
      const dropSource = document.querySelector("#gm-drop-source");
      const dropItem = document.querySelector("#gm-drop-item");
      const dropRate = document.querySelector("#gm-drop-rate");
      const dropStatus = document.querySelector("#gm-drop-rate-status");
      const dropClear = document.querySelector("#gm-drop-clear");
      let dropRateData = null;
      let dropRateRequest = 0;

      const kindLabel = { monster: "怪物", mvp: "Boss", equipment: "裝備", card: "卡片" };

      // 給物品：搜尋道具/裝備/卡片，選一筆塞進對象帳號的倉庫
      const gmItemSearch = document.querySelector("#gm-item-search");
      const gmItemSelect = document.querySelector("#gm-item-select");
      const gmKindLabel = { ...kindLabel, item: "道具" };
      const renderGmItemOptions = () => {
        // 給物品要涵蓋一般道具（藥水/材料），drop-rate 那個 searchCatalog 只找
        // 裝備跟卡片（掉落率只對那兩種設），這裡自己拼一份含 items 的搜尋。
        const q = gmItemSearch.value.trim().toLowerCase();
        const groups = [["item", S.catalog?.items], ["equipment", S.catalog?.equipment], ["card", S.catalog?.cards]];
        const matches = groups.flatMap(([kind, entries]) =>
          Object.values(entries || {})
            .filter((e) => !q || String(e.id).toLowerCase().includes(q) || String(e.name || e.id).toLowerCase().includes(q))
            .map((e) => ({ id: e.id, name: e.name || e.id, kind })),
        ).sort((a, b) => a.name.localeCompare(b.name));
        gmItemSelect.innerHTML = matches.map((x) =>
          `<option value="${esc(x.id)}">${esc(x.name)}（${gmKindLabel[x.kind]}）</option>`).join("");
      };
      gmItemSearch.oninput = renderGmItemOptions;
      renderGmItemOptions();
      document.querySelector("#gm-item-give").onclick = async () => {
        const itemId = gmItemSelect.value;
        if (!itemId) { App.toast("先選一個道具", true); return; }
        const qty = Math.max(1, Math.floor(Number(document.querySelector("#gm-item-qty").value) || 1));
        const refine = Math.max(0, Math.floor(Number(document.querySelector("#gm-item-refine").value) || 0));
        try {
          await API.adminGrantItem(targetId(), itemId, qty, refine);
          App.toast(`已給 ${itemName(itemId)} ×${qty}（進倉庫）`);
        } catch (e) { App.toast(e.detail || "失敗", true); }
      };

      const formatRate = (value) => {
        if (value == null) return "未設定";
        const rate = Number(value);
        const pct = Number.isInteger(rate * 100)
          ? String(rate * 100)
          : (rate * 100).toFixed(4).replace(/0+$/, "").replace(/\.$/, "");
        return `${rate}（${pct}%）`;
      };
      const selectedName = (group, id) => S.catalog?.[group]?.[id]?.name || id;
      const sourceName = (id) => selectedName(S.catalog?.mvps?.[id] ? "mvps" : "monsters", id);

      const renderDropOptions = () => {
        const sourceId = dropSource.value;
        const itemId = dropItem.value;
        const matches = dropView.searchCatalog(S.catalog, dropSourceSearch.value);
        dropSource.innerHTML = `<option value="">全域（不指定來源）</option>` +
          matches.sources.map((x) => `<option value="${esc(x.id)}">${esc(x.name)}（${kindLabel[x.kind]}）</option>`).join("");
        if (matches.sources.some((x) => x.id === sourceId)) dropSource.value = sourceId;
        const itemMatches = dropView.searchCatalog(S.catalog, dropItemSearch.value);
        dropItem.innerHTML = itemMatches.items.map((x) =>
          `<option value="${esc(x.id)}">${esc(x.name)}（${kindLabel[x.kind]}）</option>`).join("");
        if (itemMatches.items.some((x) => x.id === itemId)) dropItem.value = itemId;
      };
      const renderDropRate = (data) => {
        if (!data) {
          dropStatus.innerHTML = `<p class="muted">${dropItem.value ? "載入中…" : "找不到符合的裝備或卡片"}</p>`;
          dropClear.disabled = true;
          return;
        }
        const source = dropSource.value;
        const sourceText = source ? `${esc(sourceName(source))}（${esc(source)}）` : "全域（所有來源）";
        dropStatus.innerHTML = `
          <div class="kv"><span class="k">來源</span><span>${sourceText}</span></div>
          <div class="kv"><span class="k">物品</span><span>${esc(selectedName(dropItem.value && S.catalog?.cards?.[dropItem.value] ? "cards" : "equipment", dropItem.value))}</span></div>
          <div class="kv"><span class="k">目前有效率</span><span>${formatRate(data.effective_rate)}</span></div>
          <div class="sub">內容基準 ${formatRate(data.content_rate)} ・ 全域覆寫 ${formatRate(data.global_rate)} ・ 來源覆寫 ${formatRate(data.source_rate)}</div>`;
        const override = source ? data.source_rate : data.global_rate;
        dropRate.value = override == null ? (data.effective_rate ?? "") : override;
        dropClear.disabled = override == null;
      };
      const loadDropRate = async () => {
        const itemId = dropItem.value;
        const sourceId = dropSource.value || null;
        const request = ++dropRateRequest;
        dropRateData = null;
        renderDropRate(null);
        if (!itemId) return;
        try {
          const data = await API.adminDropRates(itemId, sourceId);
          if (request !== dropRateRequest) return;
          dropRateData = data;
          renderDropRate(data);
        } catch (e) {
          if (request !== dropRateRequest) return;
          dropStatus.innerHTML = `<p class="muted">${esc(e.detail || "載入失敗")}</p>`;
          dropClear.disabled = true;
        }
      };

      dropSourceSearch.oninput = () => { renderDropOptions(); loadDropRate(); };
      dropItemSearch.oninput = () => { renderDropOptions(); loadDropRate(); };
      dropSource.onchange = loadDropRate;
      dropItem.onchange = loadDropRate;
      document.querySelector("#gm-drop-save").onclick = async () => {
        const itemId = dropItem.value;
        const sourceId = dropSource.value || null;
        if (!itemId) { App.toast("請先選擇裝備或卡片", true); return; }
        if (!dropView.isValidRate(dropRate.value)) {
          App.toast("掉落率必須是 0 到 1", true);
          return;
        }
        try {
          await API.adminSetDropRate(itemId, Number(dropRate.value), sourceId);
          App.toast("掉落率已設定");
          await loadDropRate();
        } catch (e) { App.toast(e.detail || "設定失敗", true); }
      };
      dropClear.onclick = async () => {
        const itemId = dropItem.value;
        const sourceId = dropSource.value || null;
        const override = sourceId ? dropRateData?.source_rate : dropRateData?.global_rate;
        if (!itemId || override == null) { App.toast("目前沒有可清除的覆寫", true); return; }
        try {
          await API.adminDeleteDropRate(itemId, sourceId);
          App.toast("已清除掉落率覆寫");
          await loadDropRate();
        } catch (e) { App.toast(e.detail || "清除失敗", true); }
      };
      renderDropOptions();
      await loadDropRate();

      await showSettings();
      await showOnline();
      API.announcement().then((a) => {
        const el = document.querySelector("#gm-ann");
        if (el && a) el.value = a.text || "";
      }).catch(() => {});
    },
  };
})();
