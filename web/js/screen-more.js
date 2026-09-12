// screen-more — MVP 挑戰 / 面對面交易 / GM 面板 / 登出
(() => {
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
          el.innerHTML = lines.join("\n");
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
        el.innerHTML = lines.slice(0, i + 1).join("\n");
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
          if (flog) { flog.hidden = false; flog.innerHTML = lf.lines.join("\n"); }
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
      const fmt = (arr) => arr.length
        ? arr.map((i) => i.item_id
            ? `${esc(itemName(i.item_id))} ×${i.qty}`
            : `裝備 #${i.equipment_id}`).join("、")
        : "（空）";
      const done = t.status !== "open";
      let inv = { items: {}, equipment: [] };
      if (!done) { try { inv = await API.inventory(S.char.id); } catch (_) {} }
      const itemBtns = Object.entries(inv.items || {}).map(([id, qty]) =>
        `<button class="btn small" data-put-item="${esc(id)}">${esc(itemName(id))} ×${qty}</button>`).join("");
      const eqBtns = (inv.equipment || []).filter((e) => !e.equipped_slot).map((e) =>
        `<button class="btn small" data-put-eq="${e.id}">${esc(itemName(e.equipment_id))} +${e.refine || 0}</button>`).join("");

      box.innerHTML = `
        <div class="card" style="margin-top:10px">
          <div class="kv"><span class="k">交易 #${t.id}</span><span class="pill">${esc(t.status)}</span></div>
          <div class="kv"><span class="k">對象</span><span>${esc(
            this._side === "from" ? (t.to_name || "？") : (t.from_name || "？"))}</span></div>
          <div class="kv"><span class="k">我方放上</span><span>${fmt(mine)}</span></div>
          <div class="kv"><span class="k">對方放上</span><span>${fmt(theirs)}</span></div>
          ${done ? "" : `
          <p class="muted" style="margin-top:8px">點道具 / 裝備放入（道具會問數量）</p>
          <div class="row tight">${itemBtns || "<span class='muted'>沒有道具</span>"}</div>
          <div class="row tight" style="margin-top:4px">${eqBtns || "<span class='muted'>沒有可交易裝備</span>"}</div>`}
          <div class="row" style="margin-top:10px">
            <button class="btn primary" id="trade-confirm"${done ? " disabled" : ""}>確認</button>
            <button class="btn" id="trade-cancel"${done ? " disabled" : ""}>取消</button>
            <button class="btn ghost" id="trade-refresh">重新整理</button>
          </div>
        </div>`;

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
        <div class="section-title" style="margin-top:10px"><span class="k">我的角色</span></div>
        <div class="row">
          <input id="gm-zeny" type="number" placeholder="給 Zeny（可負）" style="flex:1">
          <button class="btn small" id="gm-money">給錢</button>
        </div>
        <div class="row" style="margin-top:6px">
          <input id="gm-be" type="number" placeholder="base_exp" style="flex:1">
          <input id="gm-je" type="number" placeholder="job_exp" style="flex:1">
          <button class="btn small" id="gm-xp">設經驗</button>
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
      document.querySelector("#gm-money").onclick = async () => {
        try {
          await API.adminMoney(S.char.id, Number(document.querySelector("#gm-zeny").value) || 0);
          App.toast("已給錢"); await App.refreshChar();
        } catch (e) { App.toast(e.detail || "失敗", true); }
      };
      document.querySelector("#gm-xp").onclick = async () => {
        try {
          await API.adminExperience(S.char.id, Number(document.querySelector("#gm-be").value) || 0, Number(document.querySelector("#gm-je").value) || 0);
          App.toast("已設經驗"); await App.refreshChar();
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
