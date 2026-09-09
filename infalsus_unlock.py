#!/usr/bin/env python3
"""In Falsus - unlock all story-gated songs (save-state patcher).

What it does
------------
In Falsus gates 61 of its songs behind Scenario progress: reading a story
segment grants the songs listed for it in the game's RewardData asset.
This tool rewrites the story-progress dictionary inside savestate_V3.sav so
every story segment counts as read, which unlocks those songs.

The original save is backed up automatically next to itself before anything is
written, and the untouched remainder of the file is preserved byte for byte.

Usage
-----
    python infalsus_unlock.py            # patch (disclaimer + confirm, then backup)
    python infalsus_unlock.py info       # show current story progress
    python infalsus_unlock.py diag       # dump diagnostics for an unknown layout
    python infalsus_unlock.py restore    # undo, from the backup
    python infalsus_unlock.py patch FILE # patch a specific save file
    python infalsus_unlock.py patch --force   # rewrite even if already patched
    python infalsus_unlock.py patch --yes     # skip the confirmation prompt

Only standard-library Python 3.8+ is required.
"""
import base64
import glob
import os
import shutil
import struct
import sys
import zlib

# --- story segment ids, delta + zlib + base64 encoded (236 entries) ---
_IDS_B64 = "eNpdUj1PAkEQfZiDWxICVxA5Ks5gpKUy/gxLOrXyOuig26us/QmW/BT/gokF5RUmbGFyW5CsMzu7J1rs3e58vHnzZjbqI99rQAH+c0iBDHLqcLfP4ufD/vhQKsQ90KfqtfYsYJmQF99100ERfdsbWNeDquCPTQXPrH/xsw1hkq/WweaDgJzjznhgRS6dIiMOVk+QU86BcnJIbhF4899sQ/1QL6mF38kB3+6SbikSzgx9cHxGD196J/UPTeARKNm19AAQX3Q8NueqnWiyorNnviXV84T7+HKTlr89wucl6OJEfK+Zjw7Y25R4LTCulMc9NT0MMKU+oyaXPragip+aDFXqsQbVkGJY7yGM4/6EG+tpNfkcs7+SPuyth+J5YydcGF9VSSt7Rnajpc/sTD/eDRtmkW/6FNNtd4Nj2M/ziPvl9TvKLED98py4XvFvt/6ce3je7duMRd+4k054cR2OY55G9whz2ubxHGOPzN/PjO3NnOwX0qMdUcQyxA9pnzpnu3gX7DP6LVG7tNWGL4UZkWZP7Vwe7Tx5ZY2svEu78H2+Bd3iDnJ+sZLevZ4RTwnXknrfuxea4Qxl9Z78AOg4mCo="

COUNT_OFF = 105122
ENTRIES_OFF = 105126
STRIDE = 20
SENTINEL = 0x02


def _setup_output():
    """Make Chinese output safe on every console.

    Windows consoles often use a legacy code page (GBK/CP936) where non-ASCII
    text either mojibakes or raises UnicodeEncodeError. Prefer UTF-8, fall back
    to replacing unencodable characters instead of crashing.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            try:
                stream.reconfigure(errors="replace")
            except Exception:
                pass


def story_ids():
    raw = zlib.decompress(base64.b64decode(_IDS_B64))
    out, cur = [], 0
    for i in range(0, len(raw), 4):
        cur += struct.unpack_from("<i", raw, i)[0]
        out.append(cur)
    return out


def candidate_saves():
    home = os.path.expanduser("~")
    pats = []
    if os.name == "nt":
        pats.append(os.path.join(os.environ.get("USERPROFILE", home),
                                 "AppData", "LocalLow", "lowiro", "infalsus"))
    elif sys.platform == "darwin":
        pats.append(os.path.join(home, "Library", "Application Support",
                                 "lowiro", "infalsus"))
    else:
        pats.append(os.path.join(home, ".config", "unity3d", "lowiro", "infalsus"))
        pats.append(os.path.join(home, ".local", "share", "unity3d", "lowiro", "infalsus"))
    found = []
    for base in pats:
        for p in glob.glob(os.path.join(base, "**", "savestate_V3.sav"), recursive=True):
            found.append(p)
    return found


def find_save(explicit=None):
    if explicit:
        return explicit
    hits = candidate_saves()
    if not hits:
        return None
    # prefer the most recently modified
    hits.sort(key=os.path.getmtime, reverse=True)
    return hits[0]


def parse(b, count_off=COUNT_OFF, entries_off=ENTRIES_OFF):
    if len(b) < entries_off:
        raise ValueError("file too small to be an In Falsus save")
    cnt = struct.unpack_from("<i", b, count_off)[0]
    if not (0 <= cnt <= 100000):
        raise ValueError("unexpected entry count %d - save layout changed?" % cnt)
    entries = []
    for k in range(cnt):
        o = entries_off + k * STRIDE
        if o + STRIDE > len(b):
            raise ValueError("entry table runs past end of file")
        entries.append(dict(
            off=o,
            id=struct.unpack_from("<i", b, o)[0],
            lines=struct.unpack_from("<i", b, o + 8)[0],
            isread=b[o + 12],
            challenge=b[o + 13],
            ff=b[o + 14],
        ))
    return cnt, entries


def locate_dict(b, ids=None):
    """Find the story dictionary, preferring the known offset.

    Returns (count_off, entries_off, marker_off) or raises ValueError with a
    helpful message.
    """
    if len(b) >= ENTRIES_OFF:
        try:
            cnt, entries = parse(b)
            if cnt > 0 and all(0x17000000 <= e["id"] <= 0x1A000000
                               for e in entries[:5]):
                return COUNT_OFF, ENTRIES_OFF, COUNT_OFF - 1
        except ValueError:
            pass

    cands = find_dict(b, ids)
    if not cands:
        raise ValueError(
            "未能在存档中定位剧情进度表（存档版本可能不同）。\n"
            "请用 diag 命令导出诊断信息反馈。")
    best = cands[0]
    return best["marker"] + 1, best["entries"], best["marker"]


def read(path):
    with open(path, "rb") as f:
        return bytearray(f.read())


def backup_path(path):
    return path + ".orig"


def game_running():
    """Best-effort check: is In Falsus currently running?"""
    if os.name != "nt":
        return False
    try:
        import ctypes
        from ctypes import wintypes
        TH32CS_SNAPPROCESS = 0x00000002
        k32 = ctypes.windll.kernel32

        class PROCESSENTRY32(ctypes.Structure):
            _fields_ = [("dwSize", wintypes.DWORD),
                        ("cntUsage", wintypes.DWORD),
                        ("th32ProcessID", wintypes.DWORD),
                        ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
                        ("th32ModuleID", wintypes.DWORD),
                        ("cntThreads", wintypes.DWORD),
                        ("th32ParentProcessID", wintypes.DWORD),
                        ("pcPriClassBase", ctypes.c_long),
                        ("dwFlags", wintypes.DWORD),
                        ("szExeFile", ctypes.c_char * 260)]

        snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if snap == -1:
            return False
        try:
            entry = PROCESSENTRY32()
            entry.dwSize = ctypes.sizeof(PROCESSENTRY32)
            ok = k32.Process32First(snap, ctypes.byref(entry))
            while ok:
                name = entry.szExeFile.decode("mbcs", "ignore").lower()
                if name in ("infalsus.exe", "infalsus"):
                    return True
                ok = k32.Process32Next(snap, ctypes.byref(entry))
        finally:
            k32.CloseHandle(snap)
    except Exception:
        return False
    return False


def do_backup(path):
    """Create the backup once and never overwrite it.

    Overwriting the backup with an already-patched save would destroy the only
    pristine copy, so an existing backup is always kept untouched.

    Returns (backup_path, action) where action is 'created' or 'kept'.
    """
    bp = backup_path(path)
    if os.path.exists(bp):
        return bp, "kept"
    shutil.copy2(path, bp)
    return bp, "created"


def cmd_diag(path):
    """Print everything needed to diagnose an unsupported save layout."""
    b = read(path)
    ids = set(story_ids())
    print("=== 诊断信息（可整段复制发回）===")
    print("tool ver  : 2026-09-09 / layout-detect")
    print("save path : %s" % path)
    print("size      : %d bytes" % len(b))

    if len(b) >= COUNT_OFF + 4:
        cnt = struct.unpack_from("<i", b, COUNT_OFF)[0]
        print("assumed marker@%d : %s" % (COUNT_OFF - 1, hex(b[COUNT_OFF - 1])))
        print("assumed count @%d : %d" % (COUNT_OFF, cnt))
    else:
        print("file is smaller than the assumed dictionary offset")
    lo = max(0, COUNT_OFF - 16)
    hi = min(len(b), COUNT_OFF + 24)
    print("hex %d..%d : %s" % (lo, hi, b[lo:hi].hex(" ")))
    print("ascii      : %s" % "".join(chr(c) if 32 <= c < 127 else "."
                                     for c in b[lo:hi]))

    hits = 0
    first = None
    for sid in ids:
        i = b.find(struct.pack("<i", sid))
        if i >= 0:
            hits += 1
            if first is None:
                first = i
    print("known story ids present : %d / %d" % (hits, len(ids)))
    if first is not None:
        print("first story id at offset: %d" % first)

    print("--- 候选字典（严格）---")
    cands = find_dict(b, ids)
    if cands:
        for c in cands[:10]:
            print("  marker@%-8d count=%-4d entries@%-8d 已知ID %d/%d"
                  % (c["marker"], c["count"], c["entries"],
                     c["known"], c["count"]))
    else:
        print("  无")

    print("--- 宽松扫描：所有 0x02 且 count 合理的候选 ---")
    loose = 0
    for off in range(0, len(b) - 8):
        if b[off] != SENTINEL:
            continue
        c = struct.unpack_from("<i", b, off + 1)[0]
        if not (1 <= c <= 400):
            continue
        ent = off + 5
        if ent + c * STRIDE > len(b):
            continue
        n = min(c, 20)
        valid = sum(1 for k in range(n)
                    if 0x10000000 <= struct.unpack_from("<i", b, ent + k * STRIDE)[0] <= 0x2FFFFFFF)
        known = sum(1 for k in range(c)
                    if struct.unpack_from("<i", b, ent + k * STRIDE)[0] in ids)
        print("  marker@%-8d count=%-4d 合法ID %d/%d 已知ID %d/%d"
              % (off, c, valid, n, known, c))
        loose += 1
        if loose > 25:
            print("  ...（更多候选已省略）")
            break
    if loose == 0:
        print("  无")

    print("--- 任意 0x02 标记附近 20 字节（最多 10 处）---")
    shown = 0
    for off in range(0, len(b) - 25):
        if b[off] != SENTINEL:
            continue
        c = struct.unpack_from("<i", b, off + 1)[0]
        if 1 <= c <= 400:
            continue          # already reported above
        print("  @%-8d %s" % (off, b[off:off + 20].hex(" ")))
        shown += 1
        if shown >= 10:
            break
    if shown == 0:
        print("  无")
    print("=== 诊断结束 ===")


def find_dict(b, ids=None):
    """Locate the story-progress dictionary without relying on a fixed offset.

    Returns a list of candidates, best first:
        dict(marker=..., count=..., entries=..., known=..., valid=...)
    A candidate is the 0x02 marker byte, a plausible entry count, and a run of
    20-byte entries whose first int32 looks like a StoryIdentifier.
    """
    if ids is None:
        ids = set(story_ids())
    else:
        ids = set(ids)
    out = []
    limit = len(b) - 8
    for off in range(0, limit):
        if b[off] != SENTINEL:
            continue
        c = struct.unpack_from("<i", b, off + 1)[0]
        if not (1 <= c <= 400):
            continue
        ent = off + 5
        if ent + c * STRIDE > len(b):
            continue
        n = min(c, 40)
        valid = 0
        known = 0
        for k in range(n):
            eid = struct.unpack_from("<i", b, ent + k * STRIDE)[0]
            if 0x17000000 <= eid <= 0x1A000000:
                valid += 1
            if eid in ids:
                known += 1
        if valid < n * 0.9:
            continue
        # full-file count of known ids, for ranking
        known_all = 0
        for k in range(c):
            eid = struct.unpack_from("<i", b, ent + k * STRIDE)[0]
            if eid in ids:
                known_all += 1
        out.append(dict(marker=off, count=c, entries=ent,
                        valid=valid, known=known_all))
    out.sort(key=lambda d: (-d["known"], -d["valid"], -d["count"]))
    return out


def cmd_info(path):
    b = read(path)
    ids = story_ids()
    count_off, entries_off, marker_off = locate_dict(b, ids)
    cnt, entries = parse(b, count_off, entries_off)
    print("save file :", path)
    print("size      :", len(b), "bytes")
    print("dict at   :", marker_off, "(auto-detected)")
    print("entries   :", cnt, "of", len(ids))
    read_n = sum(1 for e in entries if e["isread"])
    print("read      : %d / %d story segments" % (read_n, len(ids)))
    if cnt >= len(ids):
        print("status    : patched (all segments present)")
    for e in entries[:15]:
        print("   id=%-10d lines=%-8d read=%d challenge=%d ff=%d"
              % (e["id"], e["lines"], e["isread"], e["challenge"], e["ff"]))
    if cnt > 15:
        print("   ... %d more" % (cnt - 15))


def confirm_disclaimer(path, assume_yes=False):
    """Show the disclaimer and require explicit confirmation before writing.

    Returns True only when the user clearly agrees. Defaults to False on
    anything ambiguous, on EOF, or in non-interactive runs (unless --yes).
    """
    print("=" * 60)
    print("  免责声明")
    print("=" * 60)
    print("  本工具仅修改本地存档中的「剧情进度」数据，用于解锁受剧情限制的歌曲。")
    print("  它不会修改游戏本体，也不会联网上传任何内容。")
    print()
    print("  但请注意：")
    print("    - 修改存档属于非官方手段，官方未对此做任何背书；")
    print("    - 不排除日后官方加入存档校验或检测机制，导致存档异常、")
    print("      成就失效甚至账号受限（封禁）的可能；")
    print("    - 由此产生的一切后果由使用者自行承担。")
    print()
    print("  使用前请先备份存档（本工具也会自动备份原始存档）。")
    print("=" * 60)
    print("  目标存档：%s" % path)
    print("=" * 60)
    print()

    if assume_yes:
        print("已通过 --yes 参数确认，继续执行。")
        print()
        return True

    try:
        interactive = bool(sys.stdin and sys.stdin.isatty())
    except Exception:
        interactive = False
    if not interactive:
        print("当前为非交互环境，未做任何修改。")
        print("确认同意后请加 --yes 参数重新运行，例如：")
        print("  infalsus_unlock.exe patch --yes")
        return False

    while True:
        try:
            ans = input("是否修改游戏存档？(y/n): ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            print("已取消，未做任何修改。")
            return False
        if ans in ("y", "yes"):
            print()
            return True
        if ans in ("n", "no", ""):
            print()
            print("已取消，未做任何修改。")
            return False
        print("请输入 y 或 n。")


def cmd_patch(path, force=False, assume_yes=False):
    b = read(path)
    ids = story_ids()
    count_off, entries_off, marker_off = locate_dict(b, ids)
    cnt, entries = parse(b, count_off, entries_off)

    if cnt >= len(ids) and not force:
        print("存档已经是解锁状态（%d 条剧情记录），无需修改。" % cnt)
        print("如需强制重写，加 --force 参数。")
        return 0

    if game_running():
        print("[×] 检测到 In Falsus 正在运行，已中止，未做任何修改。")
        print("    请先完全退出游戏（并等 Steam 同步完成），再重新运行本工具。")
        print("    原因：游戏退出时会用内存里的存档覆盖本次改动。")
        return 1

    if not confirm_disclaimer(path, assume_yes=assume_yes):
        return 0

    # --- 自动备份（只创建一次，绝不覆盖已有的原始备份）---
    bp, action = do_backup(path)
    print("[1/3] 自动备份完成")
    print("      原始存档备份：%s" % bp)
    if action == "created":
        print("      备份状态：新建（这是未修改前的原始存档）")
    else:
        print("      备份状态：已存在，保留原有备份未覆盖")
        print("                （该备份是首次运行时的原始存档，restore 会还原到它）")
    print()

    rest = bytes(b[entries_off + cnt * STRIDE:])

    # 保留存档里出现过的、我们列表中没有的剧情 ID，避免丢掉未知进度
    known = set(ids)
    extra = []
    for e in entries:
        if e["id"] not in known and 0x17000000 <= e["id"] <= 0x1A000000:
            extra.append(e["id"])
    all_ids = list(ids) + extra

    body = bytearray()
    for sid in all_ids:
        rec = bytearray(STRIDE)
        struct.pack_into("<i", rec, 0, sid)
        struct.pack_into("<i", rec, 8, 999999)   # MaxLineCountRead
        rec[12] = 1                              # IsRead
        rec[13] = 1                              # HasPlayedSongChallenge
        rec[14] = 1                              # HasAllowedFastForwardSkipping
        body += rec

    out = bytearray(b[:count_off])
    out += struct.pack("<i", len(all_ids))
    out += body
    out += rest

    with open(path, "wb") as f:
        f.write(out)

    print("[2/3] 存档修改完成")
    print("      剧情进度表位置：%d（自动检测）" % marker_off)
    print("      剧情记录：%d -> %d 条%s"
          % (cnt, len(all_ids),
             ("（含 %d 条原存档独有记录）" % len(extra)) if extra else ""))
    print("      文件大小：%d -> %d 字节" % (len(b), len(out)))
    print("      存档路径：%s" % path)
    print()
    print("[3/3] 全部完成 [OK]")
    print("      " + "=" * 52)
    print("      存档修改完成，已自动备份原始存档。")
    print("      备份位置：%s" % bp)
    print("      现在可以启动 In Falsus，到选曲 / 章节包界面查看。")
    print("      " + "=" * 52)
    print()
    print("提示：")
    print("  - 想还原原始存档：python %s restore" % os.path.basename(__file__))
    print("  - 若 Steam Cloud 询问保留哪份存档，请选“本地 / 较新”的那份。")
    return 0


def cmd_restore(path):
    bp = backup_path(path)
    if not os.path.exists(bp):
        print("未找到备份文件：%s" % bp)
        return 1
    if game_running():
        print("警告：检测到 In Falsus 正在运行，请先退出游戏再还原。")
        return 1
    shutil.copy2(bp, path)
    print("已还原 [OK]")
    print("      存档路径：%s" % path)
    print("      来源备份：%s" % bp)
    return 0


def _pause_if_double_clicked(argv):
    """Keep the console open when launched by double-click (no arguments).

    A onefile exe closes its console the instant it exits, so a double-clicked
    run would otherwise flash the result and vanish before it can be read.
    Only the no-argument case pauses, so scripted/CLI use never blocks.
    """
    if len(argv) > 1:
        return
    try:
        if not sys.stdin or not sys.stdin.isatty():
            return
    except Exception:
        return
    try:
        input("\n按 Enter 键关闭窗口...")
    except Exception:
        pass


def main(argv):
    _setup_output()
    try:
        return _run(argv)
    finally:
        _pause_if_double_clicked(argv)


def _run(argv):
    args = [a for a in argv[1:] if not a.startswith("--")]
    force = "--force" in argv
    assume_yes = "--yes" in argv or "-y" in argv
    cmd = args[0] if args else "patch"
    explicit = args[1] if len(args) > 1 else None

    path = find_save(explicit)
    if path is None:
        print("未能自动找到 savestate_V3.sav 存档文件。")
        print("请确认游戏已安装并至少运行过一次，或手动指定路径：")
        print("  infalsus_unlock.exe patch \"D:\\路径\\savestate_V3.sav\"")
        return 1

    try:
        if cmd == "info":
            cmd_info(path)
            return 0
        if cmd == "diag":
            cmd_diag(path)
            return 0
        if cmd == "restore":
            return cmd_restore(path)
        if cmd == "patch":
            return cmd_patch(path, force=force, assume_yes=assume_yes)
        print(__doc__)
        return 1
    except PermissionError:
        print("没有写入权限：%s" % path)
        print("请先退出 In Falsus 并等 Steam 同步完成，再重试。")
        return 1
    except Exception as exc:
        print("出错：%s" % exc)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
