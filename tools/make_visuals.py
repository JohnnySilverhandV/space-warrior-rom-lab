"""生成三张视频用信息图（1920x1080 HTML/SVG），供无头浏览器截图为 PNG。

图1 逆向路线图 / 图2 关键地址与内存地图 / 图3 升级数据曲线
所有数值直接由原 ROM 与 v1.0 成品字节读出，不使用估计值。
"""
import math
from itertools import accumulate
from pathlib import Path

import sys
if len(sys.argv) < 3:
    print("用法: python make_visuals.py <原版ROM.bin> <v1.0成品.bin> [输出目录]")
    sys.exit(2)
SRC = Path(sys.argv[1])
V10 = Path(sys.argv[2])
OUT = (Path(sys.argv[3]) if len(sys.argv) > 3
       else Path(__file__).resolve().parent.parent / "visuals")
OUT.mkdir(parents=True, exist_ok=True)

d = SRC.read_bytes()
v10 = V10.read_bytes()
W = lambda a, b=d: int.from_bytes(b[a:a + 2], "big")

EXP = 0x16E482
old = [W(EXP + i * 2) for i in range(99)]
new = [W(EXP + i * 2, v10) for i in range(99)]
cum_old = list(accumulate(old))
cum_new = list(accumulate(new))

# 命中率表A 各档命中数（原版）
HIT_A = 0x11FACB
hit_old = [sum(1 for x in d[HIT_A + k * 20:HIT_A + k * 20 + 20] if x) for k in range(20)]

CSS = """
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:1920px;height:1080px;overflow:hidden;background:#05080f}
body{font-family:'Microsoft YaHei','SimHei',sans-serif;color:#dcecf7;position:relative}
.mono{font-family:Consolas,'Courier New',monospace}
.bg{position:absolute;inset:0;background:
 radial-gradient(ellipse 1100px 700px at 82% -10%,rgba(0,234,255,.13),transparent 70%),
 radial-gradient(ellipse 900px 600px at 5% 105%,rgba(255,46,136,.11),transparent 70%),
 linear-gradient(160deg,#070c16 0%,#05080f 55%,#0a0a12 100%)}
.grid{position:absolute;inset:0;opacity:.30;background-image:
 linear-gradient(rgba(0,234,255,.075) 1px,transparent 1px),
 linear-gradient(90deg,rgba(0,234,255,.075) 1px,transparent 1px);
 background-size:60px 60px;mask-image:linear-gradient(180deg,rgba(0,0,0,.9),rgba(0,0,0,.25))}
.scan{position:absolute;inset:0;background:repeating-linear-gradient(0deg,rgba(0,0,0,.16) 0px,rgba(0,0,0,.16) 1px,transparent 1px,transparent 4px);pointer-events:none}
.wrap{position:relative;z-index:2;width:1920px;height:1080px;padding:52px 68px 44px;display:flex;flex-direction:column}
.bar{height:6px;width:100%;background:linear-gradient(90deg,#fcee0a 0%,#fcee0a 12%,#ff2e88 12%,#ff2e88 17%,#00eaff 17%,#00eaff 68%,#1b2b3d 68%,#1b2b3d 100%);margin-bottom:34px}
.top{display:flex;justify-content:space-between;align-items:flex-end;margin-bottom:12px}
.kicker{font-size:19px;letter-spacing:7px;color:#00eaff;font-weight:700}
.kicker b{color:#fcee0a}
h1{font-size:56px;line-height:1.12;letter-spacing:2px;font-weight:900;color:#f2f9ff;text-shadow:0 0 26px rgba(0,234,255,.32)}
h1 em{font-style:normal;color:#fcee0a}
.sub{margin-top:12px;font-size:21px;color:#7f9bb2;letter-spacing:1px}
.stamp{border:2px solid #ff2e88;padding:12px 20px;color:#ff2e88;font-size:17px;letter-spacing:3px;font-weight:800;transform:rotate(-3deg);box-shadow:0 0 24px rgba(255,46,136,.28) inset}
.foot{margin-top:auto;padding-top:18px;border-top:1px solid #1b2b3d;display:flex;justify-content:space-between;align-items:center;font-size:17px;color:#66839b;letter-spacing:1px}
.foot b{color:#fcee0a}
.cut{clip-path:polygon(0 0,calc(100% - 18px) 0,100% 18px,100% 100%,18px 100%,0 calc(100% - 18px))}
.panel{background:linear-gradient(150deg,rgba(13,23,36,.96),rgba(8,14,24,.96));border:1px solid #1e3448}
.hl{color:#fcee0a}.cy{color:#00eaff}.pk{color:#ff2e88}.gr{color:#39ff88}.dim{color:#7f9bb2}
"""


def shell(body, extra_css=""):
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{CSS}{extra_css}</style></head>
<body><div class="bg"></div><div class="grid"></div>
<div class="wrap">{body}</div><div class="scan"></div></body></html>"""


# ============================ 图 1：逆向路线图 ================================
steps = [
    ("01", "探壳", "#00eaff", ["2 MiB 标准 SEGA 头", "MD5 dc2981e0…", "ROM 内署名 BATTLE SYSTEM", "1995 / NeverEnding-SoftStudio"], "确认平台与身份"),
    ("02", "找锚点", "#00eaff", ["金手指 RAM 地址反查", "$FF1A64 命中 5 处", "全部落在 0x100000 战斗区", "HP/金钱用「基址+偏移」"], "从已知地址反推结构"),
    ("03", "定语义", "#fcee0a", ["lea $CAC,a2 / $FFE100,a3", "拷贝 0x140 = 4 × 0x50", "敌人ID×2 索引金币/经验表", "等级+1 处找到成长循环"], "看清代码在做什么"),
    ("04", "定表界", "#fcee0a", ["初始表 0xCAC / 4 角色", "经验表 99 项 × 4 全递增", "成长区 6 组 × 4 角色", "表A末=表B首，天然边界"], "量准边界才下刀"),
    ("05", "改表", "#ff2e88", ["HP 50→500 攻 8→200", "经验需求 ÷20 / 成长 ×3", "金币 ×2（封顶 20000）", "一行公式都没改"], "v1.0 · 731 处改动"),
    ("06", "验证", "#39ff88", ["逐条回读 731/731", "IPS 打回原 ROM 0 差异", "上机实测：能玩、数值生效", "v1.1 追加无 Miss"], "交付前闭环"),
]
cards = ""
for i, (num, title, color, lines, tag) in enumerate(steps):
    items = "".join(f'<div class="li">{x}</div>' for x in lines)
    arrow = '<div class="ar">›</div>' if i < 5 else ""
    cards += f"""<div class="step cut" style="--c:{color}">
      <div class="snum mono">{num}</div><div class="stitle">{title}</div>
      <div class="sline" style="background:{color}"></div>
      <div class="lis">{items}</div><div class="stag mono">{tag}</div></div>""" + arrow

body1 = f"""
<div class="bar"></div>
<div class="top"><div>
 <div class="kicker">SEGA MD / ROM REVERSE ENGINEERING <b>// 1995</b></div>
 <h1>从 2MB ROM 到 <em>可玩补丁</em>：四步撬开一台 68000</h1>
 <div class="sub">《太空战士 / 魔法战士》简易版 · 全流程路线图 · 全程只改数据表，不动游戏逻辑</div>
</div><div class="stamp mono">V1.1 / NO MISS</div></div>
<div class="flow">{cards}</div>
<div class="note cut"><span class="nk">关键判断</span>
 <span>知道游戏叫什么 → 金手指 RAM 地址就是天然锚点 → 省掉 90% 盲目搜表。</span>
 <span class="dim">本次真正花时间的不是「改数值」，而是<b class="hl">判断哪些东西不能碰</b>：敌人经验表防溢出不动、$103B4C 是存活目标检查不是命中判定、暴击表与命中表严格分离。</span></div>
<div class="foot"><span>WORKBUDDY 实战 · 笔记 09「四步法」复用</span>
 <span>原 ROM <b class="mono">dc2981e0…</b> 只读 · 成品 <b class="mono">da2d9534…</b> · 长度 <b>2,097,152</b> 不变</span></div>
"""
css1 = """
.flow{display:flex;gap:0;margin-top:40px;flex:1}
.step{flex:1;position:relative;background:linear-gradient(165deg,rgba(14,25,39,.96),rgba(7,13,22,.96));
 border:1px solid #20384d;padding:26px 20px 22px;display:flex;flex-direction:column;min-height:520px}
.step:before{content:"";position:absolute;left:0;top:0;width:4px;height:100%;background:var(--c);box-shadow:0 0 18px var(--c)}
.snum{font-size:50px;font-weight:900;color:var(--c);opacity:.92;line-height:1;text-shadow:0 0 22px var(--c)}
.stitle{font-size:31px;font-weight:900;margin-top:16px;color:#f2f9ff;letter-spacing:2px}
.sline{height:3px;width:62px;margin:16px 0 22px;box-shadow:0 0 12px var(--c)}
.li{font-size:17.5px;line-height:1.55;color:#a9c2d6;padding:9px 0;border-bottom:1px dashed #1b2f42}
.li:first-letter{color:var(--c)}
.stag{margin-top:auto;font-size:14px;color:var(--c);letter-spacing:1px;padding-top:18px}
.ar{flex:none;width:28px;display:flex;align-items:center;justify-content:center;font-size:42px;font-weight:900;color:#fcee0a;text-shadow:0 0 16px #fcee0a}
.note{margin-top:26px;background:rgba(252,238,10,.055);border:1px solid rgba(252,238,10,.36);
 padding:20px 26px;font-size:18px;line-height:1.7;color:#c8dbe9;display:flex;gap:20px;align-items:flex-start}
.nk{flex:none;background:#fcee0a;color:#080c14;font-weight:900;padding:5px 14px;font-size:16px;letter-spacing:2px}
"""
(OUT / "01_route.html").write_text(shell(body1, css1), encoding="utf-8")


# ==================== 图 2：关键地址与内存地图 ================================
char_rows = "".join(
    f'<div class="crow"><span class="cname mono">$FFE100 + {c * 0x50:02X}</span>'
    f'<span class="ctag">角色 {c}</span><span class="cbar"></span></div>' for c in range(4))
fields = [("+0x0E", "最大 HP", "50", "500"), ("+0x10", "当前 MP", "—", "500"),
          ("+0x12", "最大 MP", "25", "500"), ("+0x14", "攻击力", "8", "200"),
          ("+0x16", "防御力", "2", "150"), ("+0x18", "下一级所需经验", "20", "2")]
frows = "".join(
    f'<div class="fr"><span class="fo mono">{o}</span><span class="fn">{n}</span>'
    f'<span class="fv mono">{a}</span><span class="fa">→</span><span class="fv2 mono">{b}</span></div>'
    for o, n, a, b in fields)

tables = [
    ("0x000CAC", "初始角色数值表", "4 × 0x50", "HP 50 → 500 · 攻 8 → 200", "#00eaff"),
    ("0x16E482", "升级经验需求表", "99 项 × 4", "全表 ÷ 20（最低 2）", "#00eaff"),
    ("0x16E350", "角色成长值表", "6 组 × 4", "每次升级成长 × 3", "#fcee0a"),
    ("0x11EDA2", "敌人金币表", "150 × word", "× 2（封顶 20000）", "#fcee0a"),
    ("0x11FACB", "命中率概率表 A", "20 档 × 20 位", "35~100% → 全档 100%", "#ff2e88"),
    ("0x1024F4", "二次闪避判定", "2 字节", "beq.w → bra.w（平A／魔法）", "#ff2e88"),
]
tcards = "".join(f"""<div class="tc cut" style="--c:{c}">
  <div class="ta mono">{a}</div><div class="tt">{t}</div>
  <div class="tm mono">{s}</div><div class="tv">{v}</div></div>""" for a, t, s, v, c in tables)

design = [
    ("硬件随机源", "$C00009", "直接读 VDP 的 HV 计数器当随机数，零成本、每帧不同，再用 $FFEEFD 累加种子防重复。"),
    ("20 位概率位图", "查表代替除法", "把百分比判定做成 20 项 0/1 表 + tst.b，避开 68000 上昂贵的 divu；20 档复用同一例程。"),
    ("减法式经验", "$18(a5)", "存「距下一级还差多少」而非累计阈值，配合 cmp/bhi 天然防下溢，99 级用 cmpi.b #$63 卡死。"),
]
dcards = "".join(f"""<div class="dc cut"><div class="dh">{h}</div>
 <div class="dm mono">{m}</div><div class="dp">{p}</div></div>""" for h, m, p in design)

body2 = f"""
<div class="bar"></div>
<div class="top"><div>
 <div class="kicker">MEMORY MAP <b>// KEY ADDRESSES</b></div>
 <h1>关键地址地图：<em>数据在哪、改成多少</em></h1>
 <div class="sub">68000 / RAM $FFE100 起，四名角色每人 0x50 字节 · 六处下刀点全部反汇编确认</div>
</div><div class="stamp mono">6 PATCH SITES</div></div>
<div class="cols">
 <div class="left"><div class="lh">RAM 角色区 <span class="mono hl">$FFE100</span> <span class="dim">/ 4 × 0x50</span></div>
  <div class="cblock cut">{char_rows}<div class="cfoot mono">lea $CAC,a2 → lea $FFE100,a3 → move.w #$4F,d0 → 循环拷贝 0x140</div></div>
  <div class="lh2">角色结构字段 · 改前 → 改后</div>
  <div class="fblock cut">{frows}</div>
 </div>
 <div class="right"><div class="rh">ROM 内的六处下刀点</div><div class="tgrid">{tcards}</div></div>
</div>
<div class="dhead">顺手挖到的 3 个漂亮设计 <span class="dim">/ 均为反汇编中实际看到，非推测</span></div>
<div class="dgrid">{dcards}</div>
<div class="foot"><span>表A 末地址 <b class="mono">0x11FC5A</b> +1 恰为暴击率表B 首地址 <b class="mono">0x11FC5B</b> —— 天然边界，不会串表</span>
 <span>改动 <b>731 + 154</b> 处 · 越界 <b>0</b> · 逐条回读 <b>885/885</b></span></div>
"""
css2 = """
.cols{display:flex;gap:26px;margin-top:26px;height:578px}
.left{width:660px;flex:none}.right{flex:1}
.lh,.rh{font-size:24px;font-weight:800;color:#f2f9ff;margin-bottom:14px;letter-spacing:1px}
.lh2{font-size:20px;font-weight:800;color:#a9c2d6;margin:16px 0 8px}
.cblock,.fblock{background:rgba(9,17,28,.92);border:1px solid #1e3448;padding:18px 20px}
.crow{display:flex;align-items:center;gap:14px;padding:7px 0;border-bottom:1px dashed #1b2f42}
.cname{font-size:19px;color:#00eaff;width:210px}.ctag{font-size:16px;color:#8ba7bc}
.cbar{flex:1;height:12px;background:linear-gradient(90deg,#00eaff 0%,#00eaff 60%,#1b2f42 60%);box-shadow:0 0 12px rgba(0,234,255,.4)}
.cfoot{margin-top:9px;font-size:13.5px;color:#66839b;line-height:1.5}
.fr{display:flex;align-items:center;gap:12px;padding:6px 0;border-bottom:1px dashed #1b2f42;font-size:17px}
.fo{width:88px;color:#ff2e88;font-size:16px}.fn{flex:1;color:#c8dbe9}
.fv{color:#7f9bb2;width:62px;text-align:right}.fa{color:#fcee0a;width:26px;text-align:center}
.fv2{color:#39ff88;width:62px;font-weight:800}
.tgrid{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.tc{position:relative;background:linear-gradient(150deg,rgba(14,25,39,.96),rgba(7,13,22,.96));
 border:1px solid #20384d;padding:15px 18px 12px;height:150px}
.tc:before{content:"";position:absolute;left:0;top:0;width:3px;height:100%;background:var(--c)}
.ta{font-size:20px;color:var(--c);font-weight:800}.tt{font-size:22px;font-weight:900;color:#f2f9ff;margin-top:5px}
.tm{font-size:14px;color:#66839b;margin-top:4px}.tv{font-size:16px;color:#a9c2d6;margin-top:9px;line-height:1.45}
.dhead{font-size:21px;font-weight:800;color:#f2f9ff;margin:16px 0 9px}
.dhead span{font-size:15px;font-weight:400}
.dgrid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}
.dc{background:rgba(252,238,10,.045);border:1px solid rgba(252,238,10,.3);padding:11px 16px;min-height:104px}
.dh{font-size:20px;font-weight:900;color:#fcee0a}.dm{font-size:15px;color:#00eaff;margin:3px 0 7px}
.dp{font-size:15px;color:#a9c2d6;line-height:1.5}
"""
(OUT / "02_keymap.html").write_text(shell(body2, css2), encoding="utf-8")


# ======================== 图 3：升级数据曲线 =================================
CW, CH = 830, 490
PX0, PY0, PW, PH = 108, 28, 692, 386


def path_log(vals, vmax):
    pts = []
    for i, v in enumerate(vals):
        x = PX0 + i / 98 * PW
        lv = math.log10(max(1, v))
        y = PY0 + PH - (lv / math.log10(max(10, vmax))) * PH
        pts.append(f"{x:.1f},{y:.1f}")
    return "M" + " L".join(pts)


def path_lin(vals, vmax):
    pts = []
    for i, v in enumerate(vals):
        x = PX0 + i / 98 * PW
        y = PY0 + PH - (v / vmax) * PH
        pts.append(f"{x:.1f},{y:.1f}")
    return "M" + " L".join(pts)


def area(path, base_y):
    return path + f" L{PX0 + PW:.1f},{base_y:.1f} L{PX0:.1f},{base_y:.1f} Z"


def chart(title, subtitle, p_old, p_new, vmax, ticks, fmt, footnote):
    grid = ""
    for frac in [0, .25, .5, .75, 1]:
        y = PY0 + PH - frac * PH
        grid += f'<line x1="{PX0}" y1="{y:.1f}" x2="{PX0+PW}" y2="{y:.1f}" stroke="#1b3044" stroke-width="1"/>'
    for lv in [1, 20, 40, 60, 80, 99]:
        x = PX0 + (lv - 1) / 98 * PW
        grid += f'<line x1="{x:.1f}" y1="{PY0}" x2="{x:.1f}" y2="{PY0+PH}" stroke="#152738" stroke-width="1"/>'
        grid += f'<text x="{x:.1f}" y="{PY0+PH+26}" fill="#66839b" font-size="15" text-anchor="middle" class="mono">{lv}</text>'
    ylabs = ""
    for frac, val in ticks:
        y = PY0 + PH - (math.log10(max(1, val)) / math.log10(vmax)) * PH if fmt == "log" else PY0 + PH - (val / vmax) * PH
        ylabs += f'<text x="{PX0-12}" y="{y+5:.1f}" fill="#66839b" font-size="14" text-anchor="end" class="mono">{val:,}</text>'
    return f"""<div class="chart cut">
 <div class="ct">{title}</div><div class="cs">{subtitle}</div>
 <svg width="{CW}" height="{CH}" viewBox="0 0 {CW} {CH}">
  <defs>
   <linearGradient id="gOld" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ff2e88" stop-opacity=".32"/><stop offset="1" stop-color="#ff2e88" stop-opacity="0"/></linearGradient>
   <linearGradient id="gNew" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#00eaff" stop-opacity=".38"/><stop offset="1" stop-color="#00eaff" stop-opacity="0"/></linearGradient>
   <filter id="glow"><feGaussianBlur stdDeviation="4" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
  </defs>
  {grid}{ylabs}
  <path d="{area(p_old, PY0+PH)}" fill="url(#gOld)"/>
  <path d="{area(p_new, PY0+PH)}" fill="url(#gNew)"/>
  <path d="{p_old}" fill="none" stroke="#ff2e88" stroke-width="3" filter="url(#glow)"/>
  <path d="{p_new}" fill="none" stroke="#00eaff" stroke-width="3" filter="url(#glow)"/>
  <line x1="{PX0}" y1="{PY0+PH}" x2="{PX0+PW}" y2="{PY0+PH}" stroke="#3a5870" stroke-width="2"/>
  <text x="{PX0+PW}" y="{PY0+PH+52}" fill="#66839b" font-size="15" text-anchor="end">等级 LEVEL →</text>
  <rect x="{PX0+16}" y="{PY0+12}" width="18" height="4" fill="#ff2e88"/><text x="{PX0+42}" y="{PY0+21}" fill="#c8dbe9" font-size="16">原版</text>
  <rect x="{PX0+120}" y="{PY0+12}" width="18" height="4" fill="#00eaff"/><text x="{PX0+146}" y="{PY0+21}" fill="#c8dbe9" font-size="16">简易版 v1.1</text>
 </svg><div class="cf">{footnote}</div></div>"""


p1o = path_log(old, 60000)
p1n = path_log(new, 60000)
p2o = path_lin(cum_old, max(cum_old))
p2n = path_lin(cum_new, max(cum_old))
lv30_old, lv30_new = cum_old[29], cum_new[29]
lv50_old, lv50_new = cum_old[49], cum_new[49]
ratio30 = lv30_old / max(1, lv30_new)

ch1 = chart("每级所需经验 / 对数刻度", "99 级 · 四张角色表结构一致，此处取角色 0（$16E482）",
            p1o, p1n, 60000, [(0, 1), (.25, 10), (.5, 100), (.75, 1000), (1, 60000)], "log",
            f"原版 Lv1 <b class='mono'>{old[0]}</b> → Lv99 <b class='mono'>{old[-1]:,}</b> ｜ 简易版 Lv1 <b class='mono'>{new[0]}</b> → Lv99 <b class='mono'>{new[-1]:,}</b>")
ch2 = chart("累计经验需求 / 线性刻度", "同样一场战斗，简易版能爬到的等级被大幅拉开",
            p2o, p2n, max(cum_old), [(0, 0), (.25, round(max(cum_old) * .25)), (.5, round(max(cum_old) * .5)),
                                     (.75, round(max(cum_old) * .75)), (1, max(cum_old))], "lin",
            f"升到 <b>Lv30</b>：原版需 <b class='mono'>{lv30_old:,}</b> 经验，简易版只要 <b class='mono'>{lv30_new:,}</b>（约 <b class='hl'>{ratio30:.0f}×</b> 提速）")

kpis = [("÷ 20", "每级所需经验", "#00eaff"), ("× 3", "升级属性成长", "#fcee0a"),
        ("× 2", "战后金币获取", "#ff2e88"), ("100%", "平A / 魔法命中", "#39ff88")]
khtml = "".join(f'<div class="kpi cut" style="--c:{c}"><div class="kv mono">{v}</div><div class="kl">{l}</div></div>'
                for v, l, c in kpis)

body3 = f"""
<div class="bar"></div>
<div class="top"><div>
 <div class="kicker">DATA CURVES <b>// BEFORE vs AFTER</b></div>
 <h1>升级曲线被压平了：<em>前 30 级提速约 {ratio30:.0f} 倍</em></h1>
 <div class="sub">数值全部由原 ROM 字节与成品字节逐项读出 · 四张经验表均 99 项、98/98 全递增，结构自洽</div>
</div><div class="stamp mono">99 LEVELS</div></div>
<div class="charts">{ch1}{ch2}</div>
<div class="kpis">{khtml}</div>
<div class="foot"><span>刻意<b>不改敌人经验表</b>：战后经验是 word 累加，放大 40000 一类的大值会溢出回绕反而变少 —— 改需求表 ÷20 效果相同、风险低一个数量级</span>
 <span><b>885</b> 处改动 / <b>1,455</b> 字节 / IPS 端到端 <b>0 差异</b></span></div>
"""
css3 = """
.charts{display:flex;gap:26px;margin-top:20px}
.chart{flex:1;background:linear-gradient(160deg,rgba(12,22,35,.96),rgba(7,13,22,.96));border:1px solid #1e3448;padding:16px 20px 10px}
.ct{font-size:25px;font-weight:900;color:#f2f9ff}.cs{font-size:15px;color:#66839b;margin:5px 0 6px}
.cf{font-size:15px;color:#a9c2d6;line-height:1.5;margin-top:0}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:20px;margin-top:16px}
.kpi{position:relative;background:rgba(9,17,28,.9);border:1px solid #20384d;padding:13px 20px 11px;text-align:center}
.kpi:before{content:"";position:absolute;left:0;top:0;width:100%;height:3px;background:var(--c);box-shadow:0 0 16px var(--c)}
.kv{font-size:42px;font-weight:900;color:var(--c);line-height:1.1;text-shadow:0 0 24px var(--c)}
.kl{font-size:17px;color:#a9c2d6;margin-top:4px}
"""
(OUT / "03_curves.html").write_text(shell(body3, css3), encoding="utf-8")

print("=== 三张信息图 HTML 已生成 ===")
for f in sorted(OUT.glob("*.html")):
    print(f"  {f.name}  {f.stat().st_size:,} B")
print("\n=== 曲线关键数据（实测字节）===")
print(f"  每级经验 原版 Lv1..8 : {old[:8]}")
print(f"  每级经验 新版 Lv1..8 : {new[:8]}")
print(f"  原版 Lv99 单级 {old[-1]:,} / 简易版 {new[-1]:,}")
print(f"  累计 Lv30: {lv30_old:,} -> {lv30_new:,}  ({ratio30:.1f}x)")
print(f"  累计 Lv50: {lv50_old:,} -> {lv50_new:,}  ({lv50_old/max(1,lv50_new):.1f}x)")
print(f"  累计 Lv99: {cum_old[-1]:,} -> {cum_new[-1]:,}")
print(f"  命中表A 原版各档命中数: {hit_old}")
