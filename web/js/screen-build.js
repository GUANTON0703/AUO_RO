// screen-build — 加點分頁：屬性加點 / 技能 / 轉職
(() => {
  const STATS = [
    ["str", "STR 力量", "物理攻擊力"],
    ["agi", "AGI 敏捷", "迴避、攻擊速度"],
    ["vit", "VIT 體質", "HP 上限、物理防禦"],
    ["int", "INT 智力", "SP 上限、魔法攻擊、魔法防禦"],
    ["dex", "DEX 靈巧", "命中率（少量攻擊、攻速）"],
    ["luk", "LUK 幸運", "爆擊率（少量攻擊）"],
  ];
  const statCost = (v) => Math.floor(v / 10) + 2;

  Screens.build = {
    _stale() { return App.state.view !== "build"; },
    async mount() {
      this._tab = this._tab || "stats";
      this._pending = {};
      for (const [k] of STATS) this._pending[k] = 0;
      this._draw();
    },

    _draw() {
      const c = S.char;
      const tab = this._tab;
      let html = `
        <div class="card">
          <div class="section-title"><h2>${esc(c.name)}</h2>
            <span class="pill">${esc(jobName(c.job_id))} Job Lv ${c.job_level}</span></div>
          <div class="row tight">
            <button class="btn small ${tab === "stats" ? "primary" : ""}" data-tab="stats">屬性加點</button>
            <button class="btn small ${tab === "skills" ? "primary" : ""}" data-tab="skills">技能</button>
            <button class="btn small ${tab === "job" ? "primary" : ""}" data-tab="job">轉職</button>
          </div>
        </div>
        <div id="build-body"></div>`;
      view().innerHTML = html;
      view().querySelectorAll("[data-tab]").forEach((b) => {
        b.onclick = () => { this._tab = b.dataset.tab; this.mount(); };
      });
      if (tab === "stats") this._drawStats();
      else if (tab === "skills") this._drawSkills();
      else this._drawJob();
    },

    // ---------- 屬性加點 ----------
    _drawStats() {
      const c = S.char;
      const avail = c.stat_points || 0;
      const spend = this._spend();
      const left = avail - spend;
      let rows = "";
      for (const [k, label, desc] of STATS) {
        const base = c["stat_" + k] || 0;
        const add = this._pending[k];
        const target = base + add;
        const cost = statCost(target);
        const canAdd = target < 99 && cost <= left;
        rows += `
          <div style="padding:6px 0;border-bottom:1px solid var(--line)">
            <div class="kv">
              <span class="k">${label}</span>
              <span>
                ${target}${add ? ` <span class="pill good">+${add}</span>` : ""}
                <button class="btn small" data-inc="${k}" ${canAdd ? "" : "disabled"}
                  style="margin-left:8px">+ (${cost})</button>
              </span>
            </div>
            <div class="sub">${desc}</div>
          </div>`;
      }
      document.querySelector("#build-body").innerHTML = `
        <div class="card">
          <h3>屬性加點</h3>
          <div class="kv"><span class="k">可用屬性點</span><span>${avail}</span></div>
          ${rows}
          <div class="kv"><span class="k">本次要花</span>
            <span>${spend} 點 / 剩 ${left}</span></div>
          <div class="row" style="margin-top:10px">
            <button class="btn primary" id="stat-submit" ${spend > 0 ? "" : "disabled"}>送出</button>
            <button class="btn ghost" id="stat-reset">洗點</button>
          </div>
        </div>`;

      document.querySelectorAll("[data-inc]").forEach((b) => {
        b.onclick = () => { this._pending[b.dataset.inc]++; this._drawStats(); };
      });
      document.querySelector("#stat-submit").onclick = async (e) => {
        e.target.disabled = true;
        const deltas = {};
        for (const [k] of STATS) if (this._pending[k] > 0) deltas[k] = this._pending[k];
        try {
          await API.allocateStats(S.char.id, deltas);
          App.toast("加點成功");
          await App.refreshChar();
          this._pending = {}; for (const [k] of STATS) this._pending[k] = 0;
          if (this._stale() || this._tab !== "stats") return;
          this._drawStats();
        } catch (err) { App.toast(err.detail || "加點失敗", true); e.target.disabled = false; }
      };
      document.querySelector("#stat-reset").onclick = async () => {
        if (!confirm("確定要洗點？所有屬性點會退回重加。")) return;
        try {
          await API.resetStats(S.char.id);
          App.toast("已洗點");
          await App.refreshChar();
          this._pending = {}; for (const [k] of STATS) this._pending[k] = 0;
          if (this._stale() || this._tab !== "stats") return;
          this._drawStats();
        } catch (err) { App.toast(err.detail || "洗點失敗", true); }
      };
    },

    _spend() {
      const c = S.char;
      let total = 0;
      for (const [k] of STATS) {
        let v = c["stat_" + k] || 0;
        for (let i = 0; i < this._pending[k]; i++) { total += statCost(v); v++; }
      }
      return total;
    },

    // ---------- 技能 ----------
    _drawSkills() {
      const c = S.char;
      const learned = c.learned_skills || {};
      const skills = Object.values(S.catalog.skills || {})
        .filter((sk) => sk.job_id === c.job_id);
      let rows = "";
      const sorted = [...skills].sort((a, b) =>
        (a.kind === b.kind ? 0 : a.kind === "active" ? -1 : 1));
      for (const sk of sorted) {
        const lv = learned[sk.id] || 0;
        const maxed = lv >= sk.max_level;
        const tag = sk.kind === "active"
          ? `<span class="pill good">主動</span>`
          : `<span class="pill">被動</span>`;
        rows += `
          <div class="item">
            <div>${tag} ${esc(sk.name)}<div class="sub">${lv} / ${sk.max_level}</div></div>
            <button class="btn small" data-skill="${sk.id}" data-next="${lv + 1}" ${maxed ? "disabled" : ""}>學 +1</button>
          </div>`;
      }
      if (!skills.length) rows = `<p class="muted">這個職業沒有可學的技能。</p>`;
      document.querySelector("#build-body").innerHTML = `
        <div class="card">
          <h3>技能</h3>
          <div class="kv"><span class="k">可用技能點</span><span>${c.skill_points || 0}</span></div>
          <div class="list">${rows}</div>
          <div class="row" style="margin-top:10px">
            <button class="btn ghost" id="skill-reset">洗技能</button>
          </div>
        </div>`;

      document.querySelectorAll("[data-skill]").forEach((b) => {
        b.onclick = async () => {
          b.disabled = true;
          try {
            await API.learnSkill(S.char.id, b.dataset.skill, Number(b.dataset.next));
            App.toast("學習成功");
            await App.refreshChar();
            if (this._stale() || this._tab !== "skills") return;
            this._drawSkills();
          } catch (err) { App.toast(err.detail || "學習失敗", true); b.disabled = false; }
        };
      });
      document.querySelector("#skill-reset").onclick = async () => {
        if (!confirm("確定要洗技能？所有技能點會退回。")) return;
        try {
          await API.resetSkills(S.char.id);
          App.toast("已洗技能");
          await App.refreshChar();
          if (this._stale() || this._tab !== "skills") return;
          this._drawSkills();
        } catch (err) { App.toast(err.detail || "洗技能失敗", true); }
      };
    },

    // ---------- 轉職 ----------
    _drawJob() {
      const c = S.char;
      const targets = Object.values(S.catalog.jobs || {})
        .filter((j) => j.parent_id === c.job_id);
      let rows = "";
      for (const j of targets) {
        const ok = c.job_level >= j.change_job_level;
        rows += `
          <div class="item">
            <div>${esc(j.name)}<div class="sub">需 Job Lv ${j.change_job_level}</div></div>
            ${ok
              ? `<button class="btn small primary" data-job="${j.id}" data-name="${esc(j.name)}">轉職</button>`
              : `<span class="pill warn">Job Lv 不足（${c.job_level}/${j.change_job_level}）</span>`}
          </div>`;
      }
      if (!targets.length) rows = `<p class="muted">目前沒有可轉的下一階職業。</p>`;
      document.querySelector("#build-body").innerHTML = `
        <div class="card"><h3>轉職</h3><div class="list">${rows}</div></div>`;

      document.querySelectorAll("[data-job]").forEach((b) => {
        b.onclick = async () => {
          if (!confirm(`確定轉職為「${b.dataset.name}」？`)) return;
          b.disabled = true;
          try {
            await API.jobchange(S.char.id, b.dataset.job);
            await App.refreshChar();
            App.toast("轉職成功");
            if (this._stale()) return;
            App.navigate("build");
          } catch (err) { App.toast(err.detail || "轉職失敗", true); b.disabled = false; }
        };
      });
    },
  };
})();
