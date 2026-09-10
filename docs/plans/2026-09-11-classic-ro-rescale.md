# 經典 RO 數值重寫

目標：把 ROtxt 從「大數值現代 RPG」拉回「小數值 + 乘法修正」的 Pre-Renewal RO 手感。
使用者定案：Phase A 完整重寫、Phase B 一轉 10 級 / 二轉 5 級。

## Phase A — 核心公式

### 玩家 ATK
現在：`(STR + (STR//10)² + DEX//5 + LUK//5 + eq.atk) × (1 + lv/50)`
改成：`STR + DEX//5 + LUK//5 + weapon_atk×(1 + STR/150) + 非武器atk + passives`
- 拿掉 `×(1 + lv/50)` 全域倍率（這是 934 ATK 的主因）
- 拿掉 `(STR//10)²`
- STR 的收益改成「乘武器攻擊」，不是加平方
- 弓：主屬性換 DEX（沿用現有 weapon_type 判斷）

### 玩家 MATK
現在：`(INT + (INT//7)² + eq.matk) × (1 + lv/50)`
改成：`INT + (INT//8)² + weapon_matk + passives`（拿掉全域倍率，平方項縮小）

### 玩家 HP / SP
現在：`(40 + lv×hp_per_level×(1.5 + lv/12)) × (1 + VIT/60)`
改成：`(40 + lv×hp_per_level×(1.2 + lv/16)) × (1 + VIT/80)`
- lv99 騎士從 ~10600 → ~7500
- SP 同樣壓 `(1.2 + lv/25)` → `(1.0 + lv/32)`

### DEF
- `data/equipment.json` 所有 defense 值 ÷ 7 取整（full_plate 90→13、aegis_plate 165→24…）
- `_dmg_reduction` 的 K：70 → 45
- build 的 def 上限：400 → 120
- 精煉 defense +1/級 維持；`refine_stat_bonus` 的 `max_hp` 拿掉（RO 精煉不加血）

### 怪物
`monster_stats.baseline`：
- `hp_base = 40 + 12×level + 0.9×level²`（linear 項砍半）
- `atk_base = 5 + 2.0×level + 0.015×level²`（配合玩家 ATK 下降）
- `hit_base`、`flee_base`、`def_base` 維持（DEF 尺度靠 _dmg_reduction 調）
- `_ROLE` 的 def_mult 不變，但因為 def_base 是 0.6×level（小值），boss def_mult 2.1 → lv90 = 113，仍要靠 MVP 手寫值覆蓋

### MVP（mvps.json 手寫 stats）
- max_hp：大致 ÷ 2（玩家傷害掉約一半）
- atk：÷ 1.5
- defense：全部重設成 `baseline(lv,"boss").defense`（小值）
- 用腳本批次改，保留手寫 lore/drops

## Phase B — 技能等級結構

- 一轉技能：max_level 5 → 10，數值陣列從 5 個內插成 10 個（線性），sp_cost 同步
- 二轉 / 轉生二轉：維持 5 級
- max_level 1 的技能（狂暴、隱匿…）維持 1
- `stat_points_available` / `skill_points_available` 不受影響（用 sum(learned.values())）
- 前端 `groupSkillsByTier`、加點驗證不用改

## Phase C — 職業細節

- 二轉 Job 上限 70 → 50（`_JOB_CAP["second"] = 50`）；轉生二轉維持
- `dual_wield` 拆 `right_hand_mastery`（加 ATK）+ `left_hand_mastery`（減雙持懲罰 = 加 ATK 另一半）
- `cloaking` 改成純 FLEE buff（進隱匿狀態）
- 移除 `hiding` / `back_slide` 的自訂 FLEE 加成，或降到原版數值
- `improve_dodge`（殘影）→ 主 FLEE 技能，數值提高
- 爆刺：katar crit_rate_mult 提高、AGI 對 aspd 權重提高

## 執行順序

A → 重跑所有平衡模擬 → 修測試 → 部署 → B → C。每期獨立 commit。
