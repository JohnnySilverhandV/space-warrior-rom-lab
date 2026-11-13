"""《太空战士 / 魔法战士》(MD) 简易版 v1.1「无 Miss」增量补丁生成器

在已上机验证的 v1.0 成品之上追加三类改动，原始 ROM 与 v1.0 成品均只读：

  1) 命中率概率表A  0x11FACB .. 0x11FC5A  20 档 x 20 项，全填 1（100% 命中）
     - 该表只被 $103152 引用；调用点 $1024DC(平A) / $10303A(魔法与技能)
     - 表A 末尾 0x11FC5B 正好是暴击率表B 起点，边界天然闭合，不越界
     - 表B(暴击) / $11F93B(技能追加判定，原本全 1) 一律不动
  2) $1024F4  beq.w -> bra.w   跳过平A 路径的「额外 50% 硬件闪避」
  3) $103050  beq.w -> bra.w   跳过魔法/技能路径的同型判定

只改 1 个字节操作码 x2，长度不变、栈不变、流程结构不变。
另产出「纯数据版」增量 IPS（只含表A，零代码改动）供保守选择。

用法: python tools/make_nomiss_patch.py <原版ROM.bin> <v1.0成品.bin> [输出目录]
"""
import hashlib
import json
import sys
from pathlib import Path

if len(sys.argv) < 3:
    print("用法: python make_nomiss_patch.py <原版ROM.bin> <v1.0成品.bin> [输出目录]")
    sys.exit(2)
SRC = Path(sys.argv[1])
V10 = Path(sys.argv[2])
OUT = (Path(sys.argv[3]) if len(sys.argv) > 3
       else Path(__file__).resolve().parent.parent / "out")
OUT.mkdir(parents=True, exist_ok=True)

raw = SRC.read_bytes()
v10 = V10.read_bytes()
assert len(raw) == len(v10) == 2097152, "ROM / v1.0 长度异常"
assert hashlib.md5(raw).hexdigest() == "dc2981e0f8ec52d36a8441b09b79ca49", "原 ROM 已被改动"
assert hashlib.md5(v10).hexdigest() == "64fae5b7235b2b768ad804fc8689b31f", "v1.0 成品指纹不符"

HIT_A = 0x11FACB
HIT_N = 20 * 20
CODE_PATCHES = [(0x1024F4, "平A：跳过额外 50% 硬件闪避"),
                (0x103050, "魔法/技能：跳过额外 50% 硬件闪避")]

buf = bytearray(v10)
changes = []          # (offset, old, new, tag, old_val, new_val)
regions = [(HIT_A, HIT_A + HIT_N, "命中率概率表A 20档x20项"),
           (0x1024F4, 0x1024F5, "平A 二次闪避判定"),
           (0x103050, 0x103051, "魔法二次闪避判定")]


def put_byte(off, val, tag):
    old = v10[off]
    if old == val:
        return
    buf[off] = val
    changes.append((off, bytes([old]), bytes([val]), tag, old, val))


# ---- 1) 命中率概率表A 全填 1 ------------------------------------------------
for i in range(HIT_N):
    put_byte(HIT_A + i, 1, f"命中表A 档{i // 20:02d} 位{i % 20:02d}")

# ---- 2) 两处 beq.w -> bra.w -------------------------------------------------
for off, tag in CODE_PATCHES:
    assert v10[off:off + 4] == bytes.fromhex("6700000e"), f"{hex(off)} 不是预期的 beq.w +0x0e"
    put_byte(off, 0x60, tag + "（67 beq.w -> 60 bra.w）")

# ---- 校验 --------------------------------------------------------------------
assert len(buf) == len(raw), "文件长度变了"
for off, _, _, tag, _, _ in changes:
    assert any(s <= off < e for s, e, _ in regions), f"改动越界 {hex(off)} {tag}"
for off, old, new, tag, _, _ in changes:
    assert buf[off:off + len(new)] == new, f"回读失败 {hex(off)} {tag}"
    assert v10[off:off + len(old)] == old, f"v1.0 被污染 {hex(off)} {tag}"
# v1.0 的既有改动必须原样保留：v10 与 buf 的差异集合恰等于本次改动集合
diff_v10_buf = {a for a in range(len(raw)) if v10[a] != buf[a]}
diff_changes = {o for o, *_ in changes}
assert diff_v10_buf == diff_changes, "v1.0 改动未被完整继承"

v11 = bytes(buf)


# ---- IPS ---------------------------------------------------------------------
def make_ips_from_diff(base, target, path):
    """生成 base -> target 的 IPS，合并相邻改动为连续记录。"""
    merged = []
    start = None
    chunk = bytearray()
    for a in range(len(base)):
        if base[a] != target[a]:
            if start is None:
                start = a
                chunk = bytearray()
            elif a != start + len(chunk):
                merged.append((start, bytes(chunk)))
                start = a
                chunk = bytearray()
            chunk.append(target[a])
            if len(chunk) == 65535:
                merged.append((start, bytes(chunk)))
                start = None
                chunk = bytearray()
        elif start is not None and a == start + len(chunk):
            merged.append((start, bytes(chunk)))
            start = None
            chunk = bytearray()
    if start is not None:
        merged.append((start, bytes(chunk)))
    out = bytearray(b"PATCH")
    for off, data in merged:
        assert off != 0x454F46, "IPS EOF 偏移冲突"
        out += off.to_bytes(3, "big") + len(data).to_bytes(2, "big") + data
    out += b"EOF"
    Path(path).write_bytes(bytes(out))
    return len(merged)


def apply_ips(base, ips_bytes):
    p = ips_bytes
    assert p[:5] == b"PATCH" and p[-3:] == b"EOF"
    b = bytearray(base)
    i, n = 5, 0
    while i < len(p) - 3:
        off = int.from_bytes(p[i:i + 3], "big")
        ln = int.from_bytes(p[i + 3:i + 5], "big")
        i += 5
        if ln == 0:                       # RLE
            cnt = int.from_bytes(p[i:i + 2], "big")
            b[off:off + cnt] = bytes([p[i + 2]]) * cnt
            i += 3
        else:
            b[off:off + ln] = p[i:i + ln]
            i += ln
        n += 1
    return bytes(b), n


# 三个补丁：完整 / 增量 / 纯数据增量
full_ips = OUT / "太空战士魔法战士_简易版_v1.1_无Miss.ips"
inc_ips = OUT / "v1.1_无Miss_增量补丁_从v1.0.ips"
pure = bytearray(v10)
for i in range(HIT_N):
    pure[HIT_A + i] = 1
pure_ips = OUT / "v1.1_仅查表_纯数据增量_从v1.0.ips"

n_full = make_ips_from_diff(raw, v11, full_ips)
n_inc = make_ips_from_diff(v10, v11, inc_ips)
n_pure = make_ips_from_diff(v10, bytes(pure), pure_ips)

patched = OUT / "太空战士魔法战士_简易版_v1.1_无Miss.bin"
patched.write_bytes(v11)

# ---- 端到端回读 --------------------------------------------------------------
back, r1 = apply_ips(raw, full_ips.read_bytes())
assert back == v11, "完整 IPS 打回原 ROM 与成品不一致"
back2, r2 = apply_ips(v10, inc_ips.read_bytes())
assert back2 == v11, "增量 IPS 打回 v1.0 与成品不一致"
back3, r3 = apply_ips(v10, pure_ips.read_bytes())
assert back3 == bytes(pure), "纯数据增量 IPS 回读不一致"

report = {
    "version": "v1.1 无Miss",
    "source_md5": hashlib.md5(raw).hexdigest(),
    "v10_md5": hashlib.md5(v10).hexdigest(),
    "v11_md5": hashlib.md5(v11).hexdigest(),
    "size": len(v11),
    "new_change_records": len(changes),
    "new_changed_bytes": sum(len(c[2]) for c in changes),
    "hit_table": {"start": hex(HIT_A), "length": HIT_N,
                  "end_exclusive": hex(HIT_A + HIT_N),
                  "note": "末尾 0x11FC5B 恰为暴击率表B 起点，天然边界",
                  "old_hit_per_tier": [sum(1 for x in raw[HIT_A + k * 20:HIT_A + k * 20 + 20] if x) for k in range(20)],
                  "new_hit_per_tier": [20] * 20},
    "code_patches": [{"offset": hex(o), "old": "67 00 00 0e (beq.w)",
                      "new": "60 00 00 0e (bra.w)", "tag": t} for o, t in CODE_PATCHES],
    "untouched": ["暴击率表B $11FC5B", "技能追加判定表 $11F93B（原本全 1）",
                  "敌人经验表", "等级分界表", "其余任何代码"],
    "ips_full_records": n_full, "ips_inc_records": n_inc, "ips_pure_records": n_pure,
    "end_to_end": {"full_ips_replayed_records": r1, "full_ips_byte_diff": 0,
                   "inc_ips_replayed_records": r2, "inc_ips_byte_diff": 0,
                   "pure_ips_replayed_records": r3, "pure_ips_byte_diff": 0},
    "regions": [{"start": hex(s), "end": hex(e), "name": n} for s, e, n in regions],
    "changes": [{"offset": hex(o), "old": ob.hex(), "new": nb.hex(), "tag": t}
                for o, ob, nb, t, _, _ in changes],
}
(OUT / "验证报告_v1.1_无Miss.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

print("=== v1.1 无 Miss 补丁生成完成 ===")
print(f"  原 ROM MD5      : {report['source_md5']} (未改动)")
print(f"  v1.0 MD5        : {report['v10_md5']} (未改动)")
print(f"  v1.1 MD5        : {report['v11_md5']}")
print(f"  长度            : {len(v11):,} 不变")
print(f"  新增改动        : {len(changes)} 处 / {report['new_changed_bytes']} 字节")
print(f"    其中 表A 填 1 : {sum(1 for c in changes if HIT_A <= c[0] < HIT_A + HIT_N)} 字节")
print(f"    其中 代码     : {len(CODE_PATCHES)} 字节")
print(f"  白名单区间      : {len(regions)} 个，越界 0，逐条回读 {len(changes)}/{len(changes)} 通过")
print(f"  v1.0 改动继承   : 差异集合完全一致 ✅")
print(f"  IPS             : 完整 {n_full} 段 / 增量 {n_inc} 段 / 纯数据增量 {n_pure} 段")
print(f"  端到端回读      : 完整 0 差异 / 增量 0 差异 / 纯数据 0 差异 ✅")
print(f"  命中率          : 档0 {report['hit_table']['old_hit_per_tier'][0]}/20 -> 20/20, "
      f"档19 {report['hit_table']['old_hit_per_tier'][19]}/20 -> 20/20")
