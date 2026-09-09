# 賢者 sage

## 職業數值
- parent: mage
- change_job_level: 40
- hp_per_level / sp_per_level: 6.0 / 3.0
- 定位: 以元素魔法、魔法支援與反制敵方法術為主的控場法系。

## 代表技能（挑 5 個）
- `double_casting` / 雙倍投擲 / passive；max_level: 5；效果: passive_stat, stat=matk, amount=[2,4,6,8,10]；sp_cost=[0,0,0,0,0]；原版對應招式名: Double Casting（以魔攻被動近似）
- `free_cast` / 自由施法 / passive；max_level: 10；效果: passive_stat, stat=aspd, amount=[2,4,6,8,10,12,14,16,18,20]；sp_cost=[0,0,0,0,0,0,0,0,0,0]；原版對應招式名: Free Cast
- `heavens_drive` / 地震術 / active；max_level: 5；效果: aoe, power_pct=[110,130,150,170,190]；element: earth；sp_cost=[24,28,32,36,40]；原版對應招式名: Heaven's Drive
- `spell_breaker` / 魔法拆解 / active；max_level: 5；效果: debuff, stat=matk, 幅度=[-10,-20,-30,-40,-50]%, duration_s=15；sp_cost=[10,10,10,10,10]；原版對應招式名: Spell Breaker（以降低目標 MATK 近似）
- `land_protector` / 大地防護 / active；max_level: 5；效果: buff, stat=mdef, 幅度=[5,10,15,20,25], duration_s=30；sp_cost=[45,50,55,60,65]；原版對應招式名: Land Protector（以區域魔防增益近似）

資料來源：<https://irowiki.org/classic/Sage>、<https://divine-pride.net/database/skill>
