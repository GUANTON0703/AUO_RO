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
  const SKILL_STAGE_META = [
    ["novice", "新手技能"],
    ["first", "一轉技能"],
    ["second", "二轉技能"],
  ];

  // 技能分區只讀 jobs 的 tier；技能本身仍由 catalog.skills 提供。
  function groupSkillsByTier(skills, jobs, currentJobId) {
    const currentTier = jobs[currentJobId]?.tier || "first";
    return SKILL_STAGE_META.map(([tier, label]) => ({
      tier,
      label,
      open: tier === currentTier,
      skills: skills.filter((sk) => jobs[sk.job_id]?.tier === tier),
    }));
  }

  // 這只是前端即時提示；送出後端仍由 can_learn 做最終驗證。
  function getSkillPrerequisiteState(skill, learned) {
    const levels = learned || {};
    const unmet = Object.entries(skill.requires || {})
      .filter(([id, required]) => Number(levels[id] || 0) < Number(required))
      .map(([id, required]) => ({
        id,
        required: Number(required),
        current: Number(levels[id] || 0),
      }));
    return { met: unmet.length === 0, unmet };
  }

  function getJobAncestry(jobs, currentJobId) {
    const ancestry = [];
    const seen = new Set();
    for (let jid = currentJobId; jid && !seen.has(jid); jid = jobs[jid]?.parent_id) {
      ancestry.push(jid);
      seen.add(jid);
    }
    return ancestry;
  }

  function getSkillLearnState(skill, learned, pointsAvailable, ancestry) {
    const level = Number(learned?.[skill.id] || 0);
    const visible = ancestry.includes(skill.job_id);
    const maxed = level >= skill.max_level;
    const prerequisite = getSkillPrerequisiteState(skill, learned);
    return {
      visible,
      inherited: visible && skill.job_id !== ancestry[0],
      maxed,
      prerequisite,
      locked: !maxed && !prerequisite.met,
      disabled: !visible || maxed || !prerequisite.met || Number(pointsAvailable || 0) <= 0,
    };
  }

  window.ROSkillView = {
    groupSkillsByTier,
    getSkillPrerequisiteState,
    getJobAncestry,
    getSkillLearnState,
  };

  Screens.build = {
    _stale() { return App.state.view !== "build"; },
    async mount() {
      this._tab = this._tab || "stats";
      this._pending = {};
      for (const [k] of STATS) this._pending[k] = 0;
      if (this._tab === "skills" && !this._strategy) {
        this._strategy = await API.huntStrategy(S.char.id).catch(() => ({}));
      }
      this._draw();
    },

    async _saveStrategy() {
      const s = this._strategy || {};
      try { await API.setHuntStrategy(S.char.id, s); }
      catch (err) { App.toast(err.detail || "掛機設定儲存失敗", true); }
    },

    _draw() {
      const c = S.char;
      const tab = this._tab;
      let html = `
        <div class="card">
          <div class="section-title"><h2>${esc(c.name)}</h2>
            <span class="pill">${esc(jobName(c.job_id))} Job Lv ${c.job_level}</span>
            ${c.is_rebirth ? `<span class="pill good">轉生</span>` : ""}</div>
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
      const jobs = S.catalog.jobs || {};
      const chain = getJobAncestry(jobs, c.job_id);
      const rank = (jid) => (jid === c.job_id ? 0 : 1);
      const skills = Object.values(S.catalog.skills || {})
        .filter((sk) => chain.includes(sk.job_id));
      const skillMap = {};
      for (const sk of skills) skillMap[sk.id] = sk;
      const tierCache = {};
      const tierOf = (sk, stack) => {
        if (tierCache[sk.id] != null) return tierCache[sk.id];
        const reqIds = Object.keys(sk.requires || {});
        if (!reqIds.length) return (tierCache[sk.id] = 0);
        if (stack.has(sk.id)) return 0;
        stack.add(sk.id);
        let max = 0;
        for (const rid of reqIds) {
          const parent = skillMap[rid];
          const t = parent ? tierOf(parent, stack) + 1 : 0;
          if (t > max) max = t;
        }
        stack.delete(sk.id);
        return (tierCache[sk.id] = max);
      };
      for (const sk of skills) tierOf(sk, new Set());
      const unlocks = {};
      for (const sk of skills) {
        for (const rid of Object.keys(sk.requires || {})) {
          if (!skillMap[rid]) continue;
          (unlocks[rid] = unlocks[rid] || []).push(sk.id);
        }
      }
      const sorted = [...skills].sort((a, b) =>
        (rank(a.job_id) - rank(b.job_id))
        || ((tierCache[a.id] || 0) - (tierCache[b.id] || 0))
        || (a.kind === b.kind ? 0 : a.kind === "active" ? -1 : 1));
      const strat = this._strategy || {};
      const toggles = strat.skill_toggles || {};
      const rowsById = {};
      for (const sk of sorted) {
        const lv = learned[sk.id] || 0;
        const learnState = getSkillLearnState(sk, learned, c.skill_points, chain);
        const { maxed, inherited, locked } = learnState;
        const prereq = learnState.prerequisite;
        const active = sk.kind === "active" && lv > 0;
        const idleOn = toggles[sk.id] ?? (sk.idle_default?.enabled ?? true);
        const isPrimary = strat.primary_skill_id === sk.id;
        const tag = sk.kind === "active"
          ? `<span class="pill good">主動</span>`
          : `<span class="pill">被動</span>`;
        const inheritTag = inherited ? `<span class="pill">前職</span>` : "";
        const tier = tierCache[sk.id] || 0;
        const tierTag = `<span class="pill">T${tier + 1}</span>`;
        const unlockNames = (unlocks[sk.id] || []).map((id) => skillName(id)).join("、");
        const explain = skillExplain(sk, lv);
        const req = Object.entries(sk.requires || {})
          .map(([rid, rlv]) => `${skillName(rid)} Lv${rlv}`).join("、");
        const cost = sk.kind === "active" && (sk.sp_cost || []).length
          ? `　SP ${sk.sp_cost[Math.min(Math.max(1, lv), sk.sp_cost.length) - 1]}` : "";
        const btn = maxed
          ? `<span class="pill good">已滿級</span>`
          : `<button class="btn small" data-skill="${sk.id}" data-next="${lv + 1}"
              ${learnState.disabled ? "disabled" : ""}>學 +1</button>`;
        const idleCtl = active ? `
              <div class="sub" style="margin-top:4px">
                <label style="margin-right:12px"><input type="checkbox" style="width:auto"
                  data-idle="${sk.id}" ${idleOn ? "checked" : ""}> 掛機放</label>
                <label><input type="checkbox" style="width:auto"
                  data-primary="${sk.id}" ${isPrimary ? "checked" : ""}> 設為主攻</label>
              </div>` : "";
        rowsById[sk.id] = `
          <div class="item skill-row${locked ? " skill-locked" : ""}" style="align-items:flex-start">
            <div>${tag} ${inheritTag} ${tierTag} ${esc(sk.name)}
              ${locked ? `<span class="pill bad">前置未達</span>` : ""}
              <div class="sub">Lv ${lv} / ${sk.max_level}${cost}</div>
              ${explain ? `<div class="sub">${esc(explain)}</div>` : ""}
              ${req ? `<div class="sub" style="color:var(--warn)">前置：${esc(req)}</div>` : ""}
              ${unlockNames ? `<div class="sub" style="color:var(--muted)">解鎖：${esc(unlockNames)}</div>` : ""}
              ${idleCtl}
            </div>
            ${btn}
          </div>`;
      }
      const tierOpen = this._tierOpen || (this._tierOpen = {});
      const sections = groupSkillsByTier(sorted, jobs, c.job_id).map((group) => {
        const rows = group.skills.length
          ? group.skills.map((sk) => rowsById[sk.id]).join("")
          : `<p class="muted">這個階段沒有可查看的技能。</p>`;
        const open = tierOpen[group.tier] ?? group.open;
        return `
          <details class="skill-tier" data-skill-tier="${group.tier}"${open ? " open" : ""}>
            <summary>${group.label}<span class="skill-tier-count">${group.skills.length} 個技能</span></summary>
            <div class="skill-tier-list">${rows}</div>
          </details>`;
      }).join("");
      document.querySelector("#build-body").innerHTML = `
        <div class="card">
          <h3>技能</h3>
          <div class="kv"><span class="k">可用技能點</span><span>${c.skill_points || 0}</span></div>
          <div class="skill-tiers">${sections}</div>
          <div class="row" style="margin-top:10px">
            <button class="btn ghost" id="skill-reset">洗技能</button>
          </div>
        </div>`;

      document.querySelectorAll("details[data-skill-tier]").forEach((d) => {
        d.ontoggle = () => { this._tierOpen[d.dataset.skillTier] = d.open; };
      });

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
      document.querySelectorAll("[data-idle]").forEach((cb) => {
        cb.onchange = () => {
          const s = (this._strategy = this._strategy || {});
          s.skill_toggles = { ...(s.skill_toggles || {}), [cb.dataset.idle]: cb.checked };
          this._saveStrategy();
        };
      });
      document.querySelectorAll("[data-primary]").forEach((cb) => {
        cb.onchange = () => {
          const s = (this._strategy = this._strategy || {});
          s.primary_skill_id = cb.checked ? cb.dataset.primary : null;
          this._saveStrategy();
          this._drawSkills();
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
      const jobs = S.catalog.jobs || {};
      const curTier = jobs[c.job_id]?.tier;
      const targets = Object.values(jobs).filter((j) => j.parent_id === c.job_id);
      let rows = "";
      for (const j of targets) {
        const lvOk = c.job_level >= j.change_job_level;
        const needRebirth = j.tier === "third" && !c.is_rebirth;
        rows += `
          <div class="item">
            <div>${esc(j.name)}<div class="sub">需 Job Lv ${j.change_job_level}${
              j.tier === "third" ? "、需先重生" : ""}</div></div>
            ${needRebirth
              ? `<span class="pill warn">需先重生</span>`
              : lvOk
                ? `<button class="btn small primary" data-job="${j.id}" data-name="${esc(j.name)}">轉職</button>`
                : `<span class="pill warn">Job Lv 不足（${c.job_level}/${j.change_job_level}）</span>`}
          </div>`;
      }
      if (!targets.length) rows = `<p class="muted">目前沒有可轉的下一階職業。</p>`;

      const jobCap = (window.Curve?.jobCaps?.second) || 70;
      const canRebirth = curTier === "second" && !c.is_rebirth
        && c.base_level >= 99 && c.job_level >= jobCap;
      const rebirthCard = (curTier === "second" && !c.is_rebirth) ? `
        <div class="card"><h3>重生</h3>
          <p class="sub">Base 99 + Job ${jobCap} 後可重生：等級歸 1、屬性技能全清，裝備背包 Zeny 保留。
          重生後可再轉生二轉，屬性點 +52、HP/SP 成長更高。</p>
          ${canRebirth
            ? `<button class="btn primary" id="do-rebirth">重生（不可逆）</button>`
            : `<span class="pill warn">需 Base 99 且 Job ${jobCap}（目前 ${c.base_level} / ${c.job_level}）</span>`}
        </div>` : "";

      document.querySelector("#build-body").innerHTML = rebirthCard
        + `<div class="card"><h3>轉職</h3><div class="list">${rows}</div></div>`;

      const rb = document.querySelector("#do-rebirth");
      if (rb) rb.onclick = async () => {
        if (!confirm("確定重生？等級歸 1、屬性技能全清，這一步不可逆。")) return;
        rb.disabled = true;
        try {
          await API.rebirth(S.char.id);
          await App.refreshChar();
          App.toast("重生完成，重新開始吧");
          if (this._stale()) return;
          App.navigate("build");
        } catch (err) { App.toast(err.detail || "重生失敗", true); rb.disabled = false; }
      };

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
