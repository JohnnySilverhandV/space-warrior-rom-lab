# space-warrior-rom-lab · 太空战士／魔法战士 ROM 简易版改造工具

只读分析 + 参数化补丁生成工具，为 1995 年世嘉 MD 中文 RPG《太空战士之魔法战士》制作「简易版」：更高初始数值、更快升级、更多成长与金币、平 A 与魔法不再落空。**成品是完整 ROM，直接可用，不需要补丁文件。**

> 📦 离线资料包下载：[码云 Releases](https://gitee.com/johnny-silver-hand123/space-warrior-rom-lab/releases) ｜ [GitHub Releases](https://github.com/JohnnySilverhandV/space-warrior-rom-lab/releases)

本项目是工具／补丁型，不是网站，因此不提供在线入口，也不开 GitHub Pages。

## 源码仓库

| 平台 | 地址 |
|---|---|
| Gitee（国内直连） | https://gitee.com/johnny-silver-hand123/space-warrior-rom-lab |
| GitHub | https://github.com/JohnnySilverhandV/space-warrior-rom-lab |

---

## 🆕 更新日志

### v1.1.0 — 无 Miss（2026-11-13）

- 命中率概率表 20 档全填 1，命中率 35%~100% → 全档 100%
- 跳过平 A 与魔法路径各一处「额外 50% 硬件闪避」判定
- v1.0 的 731 处数值改动全部保留

### v1.0.0 — 简易版（2026-11-13）

- 初始 HP/MP 50→500、攻击 8→200、防御 2→150
- 四张升级经验需求表整体 ÷20、24 组成长值表 ×3、敌人金币表 ×2
- 已上机实测：能玩、数值生效

---

## ✨ 功能

| 脚本 | 作用 |
|---|---|
| `tools/scan.py` | 只读反汇编与表结构扫描（`charinit` / `battle` / `table` / `exp`） |
| `tools/make_easy_patch.py` | 生成 v1.0 简易版：初始数值、经验需求、成长值、金币 |
| `tools/make_nomiss_patch.py` | 在 v1.0 之上生成 v1.1 无 Miss 增量（含纯数据保守版） |
| `tools/make_visuals.py` | 从 ROM 与成品字节读出真实数值，生成三张 1920×1080 信息图 HTML |

所有脚本**只读原 ROM**，产物写入独立输出目录；改动严格限制在反汇编确认过的白名单区间，越界直接报错。

## 🚀 使用

依赖：Python 3.10+、`capstone`（`pip install capstone`）。出图另需本机 Chrome／Edge 做无头截图。

**直接用成品（推荐）**：从 Releases 下载资料包，把 `02_改版后的文件/` 里的 `.bin` 丢进模拟器、开新游戏即可。推荐 Kega Fusion / Gens / RetroArch（Genesis Plus GX 核心）。

**用脚本复现**（需自备合法的原版 ROM）：

```bash
python tools/make_easy_patch.py  <原版ROM.bin> out/
python tools/make_nomiss_patch.py <原版ROM.bin> out/太空战士魔法战士_简易版.bin out/
python tools/make_visuals.py      <原版ROM.bin> out/太空战士魔法战士_简易版.bin visuals/
python tools/scan.py battle       <原版ROM.bin>
```

原版 ROM 校验值：大小 2,097,152 字节，MD5 `dc2981e0f8ec52d36a8441b09b79ca49`。校验值不一致说明版本不同，脚本会拒绝执行。

v1.1 成品 MD5 `da2d95343becd01a79c3da78ed8bb966`，长度与原版一致，ROM 头部未改。

## 🛠 技术要点

- **改表不改逻辑**：数值调整只碰 5 类数据表，靠金手指 RAM 地址反查到初始化例程 `$000C54` 与角色 RAM 区 `$FFE100`（4 人 × `0x50`），再顺引用定位金币表 `0x11EDA2`、经验需求表 `0x16E482` 等。
- **只压需求、不放大经验**：`+0x18` 存的是「距下一级还差多少」，先比较再相减，结构上不会下溢；敌人经验是 `add.w` 累加且含 40000 这类大值，放大反而会溢出回绕，所以「升级快」走需求表 ÷20。
- **命中与暴击分表**：`$103152` 是概率查表例程，表 A `0x11FACB`（命中）与表 B `0x11FC5B`（暴击）紧邻；语义靠调用点的失败分支判定，不是靠表形状猜。
- **验证**：逐条回读 885/885、白名单越界 0、补丁打回原 ROM 与成品逐字节 0 差异。
- **未做**：平 A／魔法全体化。战斗结算是单目标流水线（`$FF1798` 单个目标指针、`$FF17A0` 单次伤害），改成 AOE 要重写控制流与消息脚本，静态验证不了。

## 📄 License

MIT © 2026 JohnnySilverhandV

## 声明

- 仓库内**不含任何 ROM 本体或游戏素材**。资料包中的原版 ROM 仅供已合法持有原版卡带／原始介质的玩家自用，请勿用于传播、分发或商业用途。
- 本项目为个人对单机离线游戏的本地修改研究，不绕过付费、不涉及联网对战。游戏商标与版权归原权利人所有，请支持正版。
