# 十字軍 crusader

## 職業數值
- parent: swordman
- change_job_level: 40
- hp_per_level / sp_per_level: 11.0 / 1.5
- 定位: 以盾牌、長矛和聖屬性攻擊為主的前排坦克／近戰輸出。

## 代表技能（挑 5 個）
- `faith` / 信仰 / passive；max_level: 10；效果: passive_stat, stat=max_hp, amount=[100,200,300,400,500,600,700,800,900,1000]；sp_cost=[0,0,0,0,0,0,0,0,0,0]；原版對應招式名: Faith
- `holy_cross` / 聖十字攻擊 / active；max_level: 5；效果: physical_hit, power_pct=[135,170,205,240,275]；sp_cost=[7,8,9,10,11]；原版對應招式名: Holy Cross
- `grand_cross` / 聖十字審判 / active；max_level: 10；效果: aoe, power_pct=[140,180,220,260,300,340,380,420,460,500]；element: holy；sp_cost=[37,40,43,46,49,52,55,58,61,64]；原版對應招式名: Grand Cross
- `shield_boomerang` / 迴旋盾 / active；max_level: 5；效果: physical_hit, power_pct=[130,160,190,220,250]；sp_cost=[10,12,14,16,18]；原版對應招式名: Shield Boomerang
- `sacrifice` / 犧牲 / active；max_level: 5；效果: physical_hit, power_pct=[120,140,160,180,200]；sp_cost=[100,100,100,100,100]；原版對應招式名: Sacrifice（以自身 HP 換取攻擊力的原版機制近似為高費用物理攻擊）

資料來源：<https://irowiki.org/classic/Crusader>、<https://irowiki.org/wiki/Crusader>
