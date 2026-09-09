# 武僧 monk

## 職業數值
- parent: acolyte
- change_job_level: 40
- hp_per_level / sp_per_level: 7.5 / 2.0
- 定位: 以連續拳技、氣彈與高爆發單體終結技作戰的近戰格鬥家。

## 代表技能（挑 5 個）
- `iron_hand` / 鐵沙掌 / passive；max_level: 10；效果: passive_stat, stat=atk, amount=[3,6,9,12,15,18,21,24,27,30]；sp_cost=[0,0,0,0,0,0,0,0,0,0]；原版對應招式名: Iron Hand
- `finger_offensive` / 氣彈指 / active；max_level: 5；效果: physical_hit, power_pct=[150,200,250,300,350]；sp_cost=[10,12,14,16,18]；原版對應招式名: Finger Offensive
- `triple_attack` / 三連擊 / passive；max_level: 10；效果: proc, effect=extra_hit, chance_pct=[29,28,27,26,25,24,23,22,21,20]；sp_cost=[0,0,0,0,0,0,0,0,0,0]；原版對應招式名: Triple Attack
- `raging_thrust` / 猛龍誇強 / active；max_level: 5；效果: physical_hit, power_pct=[140,180,220,260,300]；sp_cost=[8,10,12,14,16]；原版對應招式名: Raging Thrust
- `ashura_strike` / 阿修羅霸凰拳 / active；max_level: 5；效果: physical_hit, power_pct=[300,400,500,600,700]；sp_cost=[1,1,1,1,1]；原版對應招式名: Asura Strike（原版消耗 SP 並依剩餘 SP 增傷，power_pct 為簡化基準）

資料來源：<https://irowiki.org/classic/Monk>、<https://irowiki.org/wiki/Monk>
