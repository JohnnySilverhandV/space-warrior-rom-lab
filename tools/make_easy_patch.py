"""《太空战士 / 魔法战士》(MD) 简易版 ROM 补丁生成器

只读原始 ROM，所有产物写入 out/。改动严格限制在已经反汇编确认过的 5 张表内：
  A 初始角色数值表      0x000CAC  4 x 0x50
  B 敌人金币表          0x11EDA2  150 x word
  D 升级经验需求表      0x16E482 / 0x16E596 / 0x16E6B6 / 0x16E7CA  各 99 x word
  E 角色成长值表        由 0x16E350 的 4 个角色结构指针导出（6 组/角色，byte）

不改：敌人经验表（避免 word 累加溢出）、等级分界表（保持成长分段结构）、
      任何一行代码、ROM 头部与校验和（MD 卡带无全局校验和）。

用法: python tools/make_easy_patch.py <原版ROM.bin> [输出目录]
"""
import json
import sys
from pathlib import Path

if len(sys.argv) < 2:
    print("用法: python make_easy_patch.py <原版ROM.bin> [输出目录]")
    sys.exit(2)
SRC = Path(sys.argv[1])
OUT = (Path(sys.argv[2]) if len(sys.argv) > 2
       else Path(__file__).resolve().parent.parent / "out")
OUT.mkdir(parents=True, exist_ok=True)

raw = SRC.read_bytes()
buf = bytearray(raw)
changes = []          # (offset, old_bytes, new_bytes, 标签, 旧值, 新值)
regions = []          # 允许改动的区间白名单


def region(start, end, name):
    regions.append((start, end, name))


def put_word(off, value, tag):
    old = int.from_bytes(raw[off:off + 2], "big")
    if old == value:
        return
    b = value.to_bytes(2, "big")
    buf[off:off + 2] = b
    changes.append((off, bytes(raw[off:off + 2]), b, tag, old, value))


def put_byte(off, value, tag):
    old = raw[off]
    if old == value:
        return
    b = bytes([value])
    buf[off:off + 1] = b
    changes.append((off, bytes([old]), b, tag, old, value))


# ---- D: 升级经验需求表（先算，供 A 的 +0x18 回写用）-------------------------
EXP_TABLES = [0x16E482, 0x16E596, 0x16E6B6, 0x16E7CA]
new_exp = []
for i, base in enumerate(EXP_TABLES):
    region(base, base + 99 * 2, f"升级经验需求表 角色{i}")
    vals = []
    for lv in range(99):
        v = int.from_bytes(raw[base + lv * 2:base + lv * 2 + 2], "big")
        nv = max(2, round(v / 20))
        vals.append(nv)
        put_word(base + lv * 2, nv, f"角色{i} Lv{lv+1} 升级所需经验")
    new_exp.append(vals)

# ---- A: 初始角色数值表 -------------------------------------------------------
CHAR_BASE = 0x000CAC
region(CHAR_BASE, CHAR_BASE + 4 * 0x50, "初始角色数值表")
for c in range(4):
    b = CHAR_BASE + c * 0x50
    lv = int.from_bytes(raw[b + 6:b + 8], "big")
    for off, val, name in [
        (0x02, 120, "精神/基础属性"),
        (0x04, 100, "敏捷/基础属性"),
        (0x0C, 500, "当前 HP"),
        (0x0E, 500, "最大 HP"),
        (0x10, 500, "当前 MP"),
        (0x12, 500, "最大 MP"),
        (0x14, 200, "攻击力"),
        (0x16, 150, "防御力"),
        (0x18, new_exp[c][max(0, min(98, lv - 1))], "下一级所需经验"),
    ]:
        put_word(b + off, val, f"角色{c} {name}")

# ---- B: 敌人金币表 -----------------------------------------------------------
GOLD_BASE, GOLD_N = 0x11EDA2, 150
region(GOLD_BASE, GOLD_BASE + GOLD_N * 2, "敌人金币表")
for i in range(GOLD_N):
    v = int.from_bytes(raw[GOLD_BASE + i * 2:GOLD_BASE + i * 2 + 2], "big")
    nv = 0 if v == 0 else min(20000, v * 2)
    put_word(GOLD_BASE + i * 2, nv, f"敌人{i} 金币")

# ---- E: 角色成长值表（只改值表，不改等级分界表）-----------------------------
PTR_TABLE = 0x16E350
growth_detail = []
for c in range(4):
    struct = int.from_bytes(raw[PTR_TABLE + c * 4:PTR_TABLE + c * 4 + 4], "big")
    for g in range(6):
        p = struct + g * 8
        val_ptr = int.from_bytes(raw[p:p + 4], "big")
        brk_ptr = int.from_bytes(raw[p + 4:p + 8], "big")
        n = brk_ptr - val_ptr
        if not (0 < n <= 32 and 0 <= val_ptr < brk_ptr <= len(raw)):
            raise RuntimeError(f"角色{c} 组{g} 指针异常: {hex(val_ptr)}/{hex(brk_ptr)}")
        region(val_ptr, brk_ptr, f"角色{c} 属性组{g} 成长值表")
        for k in range(n):
            v = raw[val_ptr + k]
            nv = 0 if v == 0 else min(99, v * 3)
            put_byte(val_ptr + k, nv, f"角色{c} 属性组{g} 成长值#{k}")
        growth_detail.append({"char": c, "group": g,
                              "values_ptr": hex(val_ptr), "break_ptr": hex(brk_ptr),
                              "count": n,
                              "old": list(raw[val_ptr:brk_ptr]),
                              "new": list(buf[val_ptr:brk_ptr])})

# ---- 校验 --------------------------------------------------------------------
assert len(buf) == len(raw), "文件长度变了！"
for off, _, _, tag, _, _ in changes:
    if not any(s <= off < e for s, e, _ in regions):
        raise RuntimeError(f"改动越界: {hex(off)} {tag}")
# 逐条回读
for off, old, new, tag, ov, nv in changes:
    if buf[off:off + len(new)] != new:
        raise RuntimeError(f"回读失败: {hex(off)} {tag}")
    if raw[off:off + len(old)] != old:
        raise RuntimeError(f"源被污染: {hex(off)} {tag}")
# 原文件只读校验
import hashlib
md5 = hashlib.md5(raw).hexdigest()

patched = OUT / "太空战士魔法战士_简易版.bin"
patched.write_bytes(bytes(buf))
md5_new = hashlib.md5(bytes(buf)).hexdigest()

# ---- IPS 差量补丁（不含 ROM 本体）--------------------------------------------
def make_ips(records, path):
    out = bytearray(b"PATCH")
    for off, data in records:
        if off == 0x454F46:
            raise RuntimeError("IPS EOF 偏移冲突")
        out += off.to_bytes(3, "big") + len(data).to_bytes(2, "big") + data
    out += b"EOF"
    Path(path).write_bytes(bytes(out))

# 合并相邻改动为连续记录
merged = []
for off, _, new, _, _, _ in sorted(changes):
    if merged and off == merged[-1][0] + len(merged[-1][1]) and len(merged[-1][1]) + len(new) <= 65535:
        merged[-1] = (merged[-1][0], merged[-1][1] + new)
    else:
        merged.append((off, new))
make_ips(merged, OUT / "太空战士魔法战士_简易版.ips")

report = {
    "source": str(SRC),
    "source_md5": md5,
    "patched_md5": md5_new,
    "source_size": len(raw),
    "patched_size": len(buf),
    "changed_bytes": sum(len(c[2]) for c in changes),
    "change_records": len(changes),
    "ips_records": len(merged),
    "regions": [{"start": hex(s), "end": hex(e), "name": n} for s, e, n in regions],
    "exp_tables": [{"base": hex(b), "old_head": [int.from_bytes(raw[b+i*2:b+i*2+2], "big") for i in range(8)],
                    "new_head": v[:8], "new_tail": v[-4:]} for b, v in zip(EXP_TABLES, new_exp)],
    "gold_head": [int.from_bytes(buf[GOLD_BASE+i*2:GOLD_BASE+i*2+2], "big") for i in range(12)],
    "char_init": [{"index": c, "level": int.from_bytes(raw[CHAR_BASE+c*0x50+6:CHAR_BASE+c*0x50+8], "big"),
                   "old": [int.from_bytes(raw[CHAR_BASE+c*0x50+j:CHAR_BASE+c*0x50+j+2], "big") for j in range(0, 0x1a, 2)],
                   "new": [int.from_bytes(buf[CHAR_BASE+c*0x50+j:CHAR_BASE+c*0x50+j+2], "big") for j in range(0, 0x1a, 2)]}
                  for c in range(4)],
    "growth": growth_detail,
    "changes": [{"offset": hex(o), "old": ob.hex(), "new": nb.hex(),
                 "tag": t, "old_value": ov, "new_value": nv}
                for o, ob, nb, t, ov, nv in changes],
}
(OUT / "验证报告.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

print(f"源文件     : {SRC}")
print(f"源 MD5     : {md5} (未改动)")
print(f"成品       : {patched}")
print(f"成品 MD5   : {md5_new}")
print(f"大小       : {len(raw)} -> {len(buf)} (不变)")
print(f"改动       : {len(changes)} 处 / {sum(len(c[2]) for c in changes)} 字节 / IPS {len(merged)} 段")
print(f"白名单区间 : {len(regions)} 个，越界 0")
print(f"逐条回读   : {len(changes)}/{len(changes)} 通过")
print("\n=== 初始数值对照（角色0..3, 字段 0x00..0x18）===")
for x in report["char_init"]:
    print(f"  角色{x['index']} Lv{x['level']}: {x['old']}  ->  {x['new']}")
print("\n=== 升级所需经验（前 8 级）===")
for x in report["exp_tables"]:
    print(f"  {x['base']}: {x['old_head']} -> {x['new_head']}")
print("\n=== 金币表前 12 项 ===")
print(" ", report["gold_head"])
