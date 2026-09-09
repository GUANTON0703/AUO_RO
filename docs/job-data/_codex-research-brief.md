# Codex 研究任務：RO 職業技能與數值

## 你的任務

從 Pre-Renewal（經典）RO 資料庫爬資料，為下列職業各產一頁 `docs/job-data/<job_id>.md`。**只新增 `docs/job-data/` 底下的檔案，不要碰任何程式或 `data/`。** 不開 worktree，直接在 docs 目錄寫。

## 要爬的職業

### 二轉 B 分支（6）
| job_id | 中文 | parent |
|---|---|---|
| crusader | 十字軍 | swordman |
| sage | 賢者 | mage |
| bard | 吟遊詩人（詩人+舞孃合併，ROtxt 無性別，技能兩邊挑代表作） | archer |
| monk | 武僧 | acolyte |
| alchemist | 鍊金術師 | merchant |
| rogue | 流氓 | thief |

### 轉生二轉（12，經典硬重置：滿99→High新手→重練）
lord_knight, paladin, high_wizard, professor, sniper, minstrel（樂師+舞者合併）, high_priest, champion, whitesmith, creator, assassin_cross, stalker

## 每頁格式（對齊 data/skills.src.json 與 data/jobs.json）

```
# <中文名> <job_id>

## 職業數值
- parent: <parent job_id>
- change_job_level: <轉職所需 job level，二轉參考 40，轉生二轉參考 50>
- hp_per_level / sp_per_level: <對齊同儕，二轉物理約 11/1.5、魔法約 6/3>
- 定位: <一兩句：這職業在戰鬥裡幹嘛>

## 代表技能（挑 5 個，別搬整棵樹）
每個技能：
- id（snake_case 英文）/ 中文名 / kind（active|passive）
- max_level（通常 5 或 10）
- 效果：只能用這些 type → physical_hit / magic_hit / aoe / heal_hp / heal_sp / buff / debuff / passive_stat / proc
  - physical_hit/magic_hit: power_pct（每級一個值的 list）
  - buff/debuff: 影響哪個 stat（atk/matk/def/mdef/hit/flee/aspd/crit/max_hp/max_sp）、幅度、duration_s
  - passive_stat: stat + amount（list）
  - proc: effect 名稱 + chance_pct（list）
- element（魔法技能才要，用 neutral/water/earth/fire/wind/poison/holy/shadow/undead/ghost）
- sp_cost（每級一個值的 list）
- 原版對應招式名（讓實作對照）

## 注意
- RO 原招式如果超出上面 9 種 effect 詞彙，就近似映射（例：石化→debuff aspd/flee；沉默→debuff matk；亞斯普迪歐→buff aspd）。近似方式寫在該技能下。
- 資料來源標在頁尾（irowiki / divine-pride / ratemyserver 之類）。
```

## 完成後

把 18 個檔案 commit（只加 docs/job-data/），訊息 `docs: RO job-data research for B-branch + transcendent`。不要 push，不要部署。
