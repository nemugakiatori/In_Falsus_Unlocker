"""In Falsus save patcher - unlock all story-gated songs.

Mechanism (verified from game data):
  RewardData.asset maps StoryIdentifier -> SongIds. Reading a story grants
  that song. Songs are therefore unlocked by story progress stored in the save.

Save layout of savestate_V3.sav:
  105121 : 0x02                dictionary marker
  105122 : int32 entry count
  105126 : entries, 20 bytes each
       +0  int32 StoryIdentifier
       +8  int32 MaxLineCountRead
       +12 byte IsRead
       +13 byte HasPlayedSongChallenge
       +14 byte HasAllowedFastForwardSkipping
  bytes after the dictionary are preserved untouched.
"""
import os, struct, shutil, sys, json

SAVE = os.path.expanduser(
    r"~\AppData\LocalLow\lowiro\infalsus\<SteamID>\release\savestate_V3.sav")
BACKUP = SAVE + ".orig"
HERE = os.path.dirname(os.path.abspath(__file__))
IDS = os.path.join(HERE, "story_ids.json")

COUNT_OFF = 105122
ENTRIES_OFF = 105126
STRIDE = 20


def read_save(path=SAVE):
    with open(path, "rb") as f:
        return bytearray(f.read())


def parse(b):
    cnt = struct.unpack_from("<i", b, COUNT_OFF)[0]
    out = []
    for k in range(cnt):
        o = ENTRIES_OFF + k * STRIDE
        out.append(dict(
            off=o,
            id=struct.unpack_from("<i", b, o)[0],
            lines=struct.unpack_from("<i", b, o + 8)[0],
            isread=b[o + 12],
            challenge=b[o + 13],
            ff=b[o + 14],
        ))
    return cnt, out


def backup():
    if not os.path.exists(BACKUP):
        shutil.copy2(SAVE, BACKUP)
    return BACKUP


def restore():
    if not os.path.exists(BACKUP):
        print("no backup at", BACKUP)
        return False
    shutil.copy2(BACKUP, SAVE)
    print("restored from backup")
    return True


def cmd_info():
    b = read_save()
    cnt, entries = parse(b)
    print("file size:", len(b))
    print("story entries:", cnt)
    for e in entries:
        print("  id=%-10d lines=%-6d read=%d challenge=%d ff=%d"
              % (e["id"], e["lines"], e["isread"], e["challenge"], e["ff"]))


def cmd_patch(dry=False):
    b = read_save()
    cnt, entries = parse(b)
    rest = bytes(b[ENTRIES_OFF + cnt * STRIDE:])
    with open(IDS, encoding="utf-8") as f:
        ids = json.load(f)

    body = bytearray()
    for sid in ids:
        rec = bytearray(STRIDE)
        struct.pack_into("<i", rec, 0, sid)
        struct.pack_into("<i", rec, 8, 999999)
        rec[12] = 1
        rec[13] = 1
        rec[14] = 1
        body += rec

    new = bytearray(b[:COUNT_OFF])
    new += struct.pack("<i", len(ids))
    new += body
    new += rest

    if dry:
        print("dry run: %d -> %d bytes, entries %d -> %d"
              % (len(b), len(new), cnt, len(ids)))
        return
    backup()
    with open(SAVE, "wb") as f:
        f.write(new)
    print("patched: entries %d -> %d, size %d -> %d"
          % (cnt, len(ids), len(b), len(new)))


def cmd_unpatch_readflags():
    """Softer variant: only flip read flags of entries already present."""
    b = read_save()
    cnt, entries = parse(b)
    backup()
    for e in entries:
        b[e["off"] + 12] = 1
        b[e["off"] + 13] = 1
        b[e["off"] + 14] = 1
        struct.pack_into("<i", b, e["off"] + 8, 999999)
    with open(SAVE, "wb") as f:
        f.write(bytes(b))
    print("patched %d existing entries" % cnt)


if __name__ == "__main__":
    c = sys.argv[1] if len(sys.argv) > 1 else "info"
    if c == "info":
        cmd_info()
    elif c == "backup":
        print("backup:", backup())
    elif c == "restore":
        restore()
    elif c == "patch":
        cmd_patch(dry=("--dry" in sys.argv))
    elif c == "patch-existing":
        cmd_unpatch_readflags()
    else:
        print(__doc__)
