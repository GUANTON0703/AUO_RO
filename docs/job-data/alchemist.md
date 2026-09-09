# 鍊金術師 alchemist

## 職業數值
- parent: merchant
- change_job_level: 40
- hp_per_level / sp_per_level: 9.0 / 2.0
- 定位: 以藥水、火焰瓶與生命體支援作戰的消耗品型遠近混合職。

## 代表技能（挑 5 個）
- `axe_mastery` / 斧頭鍛鍊 / passive；max_level: 10；效果: passive_stat, stat=atk, amount=[3,6,9,12,15,18,21,24,27,30]；sp_cost=[0,0,0,0,0,0,0,0,0,0]；原版對應招式名: Axe Mastery
- `demonstration` / 火煙瓶投擲 / active；max_level: 5；效果: aoe, power_pct=[120,150,180,210,240]；element: fire；sp_cost=[10,12,14,16,18]；原版對應招式名: Demonstration
- `acid_terror` / 強酸攻擊 / active；max_level: 5；效果: physical_hit, power_pct=[130,160,190,220,250]；sp_cost=[15,18,21,24,27]；原版對應招式名: Acid Terror
- `pharmacy` / 藥水製作 / passive；max_level: 10；效果: passive_stat, stat=luk, amount=[1,2,3,4,5,6,7,8,9,10]；sp_cost=[0,0,0,0,0,0,0,0,0,0]；原版對應招式名: Pharmacy（以製作成功率／資源效率近似）
- `alchemical_protection` / 化學保護 / active；max_level: 5；效果: buff, stat=def, 幅度=[5,10,15,20,25], duration_s=120；sp_cost=[30,35,40,45,50]；原版對應招式名: Chemical Protection（四部位裝備保護合併為 DEF 增益）

資料來源：<https://irowiki.org/classic/Alchemist>、<https://irowiki.org/wiki/Alchemist>
