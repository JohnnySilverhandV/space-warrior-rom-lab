"""太空战士/魔法战士 (MD, 2MiB) ROM 结构扫描
只读分析：绝不对源文件写入。
用法: python tools/scan.py <子命令> <ROM路径>
"""
import sys
from pathlib import Path
from capstone import Cs, CS_ARCH_M68K, CS_MODE_M68K_000

if len(sys.argv) < 3:
    print("用法: python scan.py <子命令> <ROM路径>")
    sys.exit(2)
ROM = Path(sys.argv[2])
d = ROM.read_bytes()
md = Cs(CS_ARCH_M68K, CS_MODE_M68K_000)
md.detail = True


def best_disasm(start, end, label=""):
    """68k 指令边界未知时，尝试多个对齐起点，挑有效指令最多的那条"""
    best = None
    for shift in range(-16, 17, 2):
        s = start + shift
        if s < 0:
            continue
        ins = list(md.disasm(d[s:end], s))
        # 有效 = 反汇编条数多，且落在目标窗口内的条数多
        inside = [i for i in ins if start <= i.address < end]
        score = len(inside) - sum(1 for i in inside if i.mnemonic.startswith("dc"))
        if best is None or score > best[0]:
            best = (score, s, ins)
    _, s, ins = best
    print(f"\n===== {label}  (best align from {hex(s)}) =====")
    for i in ins:
        mark = ">>" if start <= i.address < end else "  "
        print(f"{mark} {i.address:08x}  {i.bytes.hex(' '):<22s} {i.mnemonic:<9s} {i.op_str}")


def find_all(pat):
    out = []
    i = 0
    while True:
        i = d.find(pat, i)
        if i < 0:
            break
        out.append(i)
        i += 1
    return out


def cmd_charinit():
    """找把 ROM 表拷进 $FFE100 的初始化例程"""
    print("### $FFE100 引用点周边（前 0x40 / 后 0x30）###")
    for off in find_all(bytes.fromhex("00ffe100")):
        if off > 0x200000:
            continue
        best_disasm(off - 0x40, off + 0x30, f"$FFE100 @ {hex(off)}")


def cmd_battle():
    """战后经验 / 金币结算例程"""
    for s, e in [(0x100f40, 0x100ff0), (0x1010b0, 0x101130),
                 (0x100b60, 0x100bd0), (0x100fc0, 0x101000)]:
        best_disasm(s, e, f"battle {hex(s)}-{hex(e)}")


def cmd_table():
    """扫描 4 组 x 0x50 的常规角色初始数值表候选
    依据秘籍模板 0x1ADA0：
      +0x00 word 未知 / +0x02 word 最大HP / +0x04 word 当前HP / +0x06 word 等级
      +0x0C..+0x16 六个 word 属性 / +0x18 word 20
    """
    print("### 4 x 0x50 常规角色表候选（等级 1~10, HP 10~999）###")
    found = []
    for base in range(0, len(d) - 0x140, 2):
        ok = True
        groups = []
        for g in range(4):
            b = base + g * 0x50
            hp = int.from_bytes(d[b+2:b+4], "big")
            hp2 = int.from_bytes(d[b+4:b+6], "big")
            lv = int.from_bytes(d[b+6:b+8], "big")
            attrs = [int.from_bytes(d[b+j:b+j+2], "big") for j in range(0x0c, 0x18, 2)]
            if not (10 <= hp <= 999 and hp == hp2 and 1 <= lv <= 10):
                ok = False
                break
            if not all(1 <= a <= 999 for a in attrs):
                ok = False
                break
            groups.append((hp, lv, attrs))
        if ok:
            found.append((base, groups))
    for base, groups in found[:40]:
        print(f"  {hex(base)}: " + " | ".join(
            f"HP{g[0]} Lv{g[1]} {g[2]}" for g in groups))
    print(f"  共 {len(found)} 个候选")


def cmd_exp():
    """找逐级递增的经验阈值表（u16be / u32be，长单调递增）"""
    print("### 长单调递增表（>=20 项，u16be）###")
    for base in range(0, len(d) - 200, 2):
        vals = [int.from_bytes(d[base+i*2:base+i*2+2], "big") for i in range(40)]
        if vals[0] < 5 or vals[0] > 5000:
            continue
        inc = sum(1 for a, b in zip(vals, vals[1:]) if b > a)
        if inc >= 30 and vals[-1] > vals[0] * 5:
            print(f"  {hex(base)}: {vals[:12]} ... {vals[-4:]}  inc={inc}/39")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "charinit"
    {"charinit": cmd_charinit, "battle": cmd_battle,
     "table": cmd_table, "exp": cmd_exp}[cmd]()
