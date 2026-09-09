# 聖殿十字軍 paladin

## 職業數值
- parent: crusader
- change_job_level: 50
- hp_per_level / sp_per_level: 12.0 / 1.5
- 定位: 強化版十字軍，吸收傷害、保護隊友並以盾牌與聖屬性反擊。

## 代表技能（挑 5 個）
- `defender` / 防禦牆 / active；max_level: 5；效果: buff, stat=def, 幅度=[10,20,30,40,50]%, duration_s=60；sp_cost=[30,30,30,30,30]；原版對應招式名: Defender
- `pressure` / 聖壓 / active；max_level: 5；效果: magic_hit, power_pct=[150,200,250,300,350]；element: holy；sp_cost=[14,18,22,26,30]；原版對應招式名: Pressure
- `sacrifice` / 犧牲攻擊 / active；max_level: 5；效果: physical_hit, power_pct=[200,250,300,350,400]；sp_cost=[100,100,100,100,100]；原版對應招式名: Sacrifice
- `shield_chain` / 盾牌連擊 / active；max_level: 5；效果: physical_hit, power_pct=[180,240,300,360,420]；sp_cost=[28,31,34,37,40]；原版對應招式名: Shield Chain
- `gospel` / 福音 / active；max_level: 5；效果: buff, stat=max_hp, 幅度=[5,10,15,20,25]%, duration_s=60；sp_cost=[80,80,80,80,80]；原版對應招式名: Gospel（原版為敵我隨機效果，取友方耐久增益）

資料來源：<https://irowiki.org/classic/Paladin>、<https://irowiki.org/wiki/Paladin>
