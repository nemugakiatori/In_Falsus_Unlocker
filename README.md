# In Falsus Unlocker

[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An unofficial save-state patcher that unlocks the songs which *In Falsus* gates
behind Scenario (story) progress.

*In Falsus* 的非官方存档修改工具：解锁因剧情进度而被锁住的歌曲。

---

## Disclaimer / 免责声明

- This is an **unofficial, fan-made tool**. It is not affiliated with, endorsed
  by, or supported by lowiro or anyone associated with *In Falsus*.
- It only rewrites the story-progress table inside your **local save file**.
  It does **not** modify the game executable, does not patch memory, and does
  not connect to the network.
- You should own a legitimate copy of the game to use it.
- Editing save data is an unsupported modification. The developer may add save
  validation or detection in the future, which could cause save corruption,
  broken achievements, or account restrictions. **Use at your own risk; the
  author takes no responsibility for any consequences.**
- This repository contains **no game assets, no copyrighted data, and no game
  files** — only original tool source code plus a list of numeric story-entry
  identifiers.
- 本工具为非官方粉丝作品，与 lowiro 及《In Falsus》官方无关。它只修改本地存档中的
  剧情进度数据，不修改游戏本体、不改内存、不联网。请使用正版游戏。修改存档属于
  非官方手段，官方日后若加入校验/检测机制，可能导致存档异常、成就失效甚至账号受限，
  **后果自负**。本仓库不包含任何游戏资源或受版权保护的内容。

---

## How it works

*In Falsus* unlocks 61 songs through Scenario progress: the game's `RewardData`
asset maps "reading a story segment" to "grant these songs". The story is a
linear chain of 236 entries — reading one unlocks the next.

The save file `savestate_V3.sav` stores that progress as a dictionary of
20-byte records. This tool rewrites that dictionary so every story segment
counts as read, which makes the gated songs available in song select.

Everything else in the save (scores, cards, settings) is preserved byte for byte.

## Requirements

- Python **3.8+** (standard library only — no `pip install` needed)
- The game installed and launched at least once (so a save file exists)

## Usage

```bash
# Double-click friendly: shows a disclaimer, asks for confirmation, backs up, patches
python infalsus_unlock.py

# Check current progress
python infalsus_unlock.py info

# Dump diagnostics when the save layout is not recognised
python infalsus_unlock.py diag

# Undo, restoring the backup
python infalsus_unlock.py restore

# Point at a specific save file
python infalsus_unlock.py patch "D:\path\to\savestate_V3.sav"

# Skip the confirmation prompt (for scripting)
python infalsus_unlock.py patch --yes
```

A prebuilt `infalsus_unlock.exe` is attached to
[Releases](../../releases) for users without Python. Build it yourself with:

```bash
pip install pyinstaller
pyinstaller --onefile --console --name infalsus_unlock --icon icons/app.ico infalsus_unlock.py
```

## Save file location

| Platform | Path |
|----------|------|
| Windows | `%USERPROFILE%\AppData\LocalLow\lowiro\infalsus\<SteamID>\release\savestate_V3.sav` |
| macOS | `~/Library/Application Support/lowiro/infalsus/...` |
| Linux (Proton) | Steam compatdata directory under `lowiro/infalsus/...` |

The tool locates it automatically.

## Safety

- **Close the game first.** If `infalsus.exe` is running the tool aborts without
  touching anything, because the game would overwrite the change on exit.
- The original save is backed up once to `savestate_V3.sav.orig` next to itself
  and is **never overwritten afterwards**, so `restore` always returns to the
  pristine state.
- The story table is located by pattern matching rather than a fixed offset, so
  saves with slightly different layouts are still handled correctly.
- If Steam Cloud asks which copy to keep, choose **local / newer**.

## Save format reference

```
offset 105121  0x02                    dictionary marker
offset 105122  int32                   entry count
offset 105126  entries, 20 bytes each
     +0  int32  StoryIdentifier
     +8  int32  MaxLineCountRead
     +12 byte   IsRead
     +13 byte   HasPlayedSongChallenge
     +14 byte   HasAllowedFastForwardSkipping
```

The field order matches `StoryEntryStateV5` in the IL2CPP metadata. Offsets vary
between saves, which is why the tool auto-detects the table.

## Repository layout

```
infalsus_unlock.py                 main tool (self-contained)
tools/export_reward_mapping.py     dumps the story -> song mapping from game data
tools/story_ids.json               the 236 story-entry identifiers
tools/falsus_save.py               earlier debug-oriented variant
icons/app.ico                      application icon
```

## License

[MIT](LICENSE)
