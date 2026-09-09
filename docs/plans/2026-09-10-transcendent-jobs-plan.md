# Phase 3：轉生二轉 設計提案

## 目標

滿等二轉角色可以「重生」（經典硬重置），重練後轉成 12 個轉生二轉之一（領主騎士、聖殿十字軍…），拿更強的技能與成長。

## 重生機制（走簡化路線，不做 High 一轉的獨立職業）

經典 RO 的重生線是 High 新手 → High 一轉 → 轉生二轉。ROtxt 不需要把 High 一轉做成獨立職業 —— 那只是「重練同一批一轉技能」。改成：

**重生條件：** base_level 99 且 job_level 50 且目前是二轉（tier second）。

**重生動作（`POST /api/characters/{id}/rebirth`）：**
1. base_level → 1、job_level → 1、base_exp / job_exp → 0
2. 所有屬性 → 1、skill_points（carried）→ 0、learned_skills → {}
3. job_id → `novice`
4. `is_rebirth` 欄位設 1（新 migration 加欄位）
5. **保留：** 裝備、背包、Zeny、角色名

重生後照一般流程重練：novice → 一轉 → 二轉 → **轉生二轉**。轉生二轉的轉職門檻多一條 `is_rebirth == 1`。

**轉生二轉的 job 樹：** `parent_id` 直接指非轉生的二轉（lord_knight parent=knight、paladin parent=crusader…），`tier` 用 `"third"`（schema 的 Literal 已經有這個值）。`job_ancestry()` 目前就是沿 parent_id 往上走，天然支援 —— lord_knight 可學 lord_knight + knight + swordman + novice 的技能。

**轉生加成：**
- 屬性點：重生角色 `STARTER_STAT_POINTS` 從 48 → 48 + <BONUS>（經典約 +52）
- HP/SP：轉生 job 的 `hp_per_level` / `sp_per_level` 比對應二轉高 <PCT>%

## 12 個轉生二轉（parent / codex 研究檔）

| id | 中文 | parent | 研究檔 |
|---|---|---|---|
| lord_knight | 領主騎士 | knight | ✅ |
| paladin | 聖殿十字軍 | crusader | ✅ |
| high_wizard | 大巫師 | wizard | ✅ |
| professor | 教授 | sage | ✅ |
| sniper | 神射手 | hunter | ✅ |
| minstrel | 樂師（吟遊詩人轉生，合併） | bard | ✅ |
| high_priest | 大祭司 | priest | ✅ |
| champion | 拳聖 | monk | ✅ |
| whitesmith | 白色鐵匠 | blacksmith | ✅ |
| creator | 生命創造者 | alchemist | ✅ |
| assassin_cross | 十字刺客 | assassin | ✅ |
| stalker | 神行太保 | rogue | ✅ |

每職 5 個代表技能，從 codex 研究檔挑，映射到現有 effect 詞彙、數值校準到二轉的 1.3~1.5 倍。

## 分三批

- **Batch A：重生機制** — migration 加 `is_rebirth`、`/rebirth` endpoint、`change_job` 加 tier third 的 is_rebirth 門檻、stat 點加成、前端 build 頁「重生」按鈕（滿足條件才出現）+ 轉生二轉在轉職選單顯示。
- **Batch B：12 轉生 job 條目 + 60 技能** — jobs.json + skills.src.json，跟二轉 B 分支同做法。
- **Batch C：驗收** — 每職 combat smoke、轉生流程 e2e 測試、平衡。

## 要你拍板

1. 屬性點加成：+52（經典）還是別的數字？
2. 轉生 job 的 HP/SP 比二轉高幾 %？（15 / 25 / 其他）
3. 重生後 job_id 直接設 `novice` 就好，還是要一個 `high_novice` 顯示名 + 「轉生中」badge？
