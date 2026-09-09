# InFalsus-Unlocker

[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

*In Falsus* 的非官方存档修改工具：解锁因剧情进度而被锁住的歌曲。

An unofficial save-state patcher that unlocks the songs *In Falsus* gates
behind Scenario (story) progress.

---

## 使用方法

### 方式一：双击 exe（推荐，无需安装 Python）

1. 到 [Releases](../../releases) 下载 `In_Falsus_unlocker.exe`。
2. **先完全退出游戏**（任务管理器里确认没有 `infalsus.exe`）。
3. **双击 `In_Falsus_unlocker.exe`**。
4. 阅读免责声明，输入 `y` 回车确认。
5. 看到「存档修改完成，已自动备份原始存档」后按 Enter 关闭窗口，启动游戏即可。

工具会自动定位存档、自动备份、自动完成修改，不需要其他操作。

### 方式二：用 Python 运行

需要 Python **3.8+**（仅用标准库，无需 `pip install`）。

```bash
# 直接运行：显示免责声明 → 询问确认 → 自动备份 → 修改
python infalsus_unlock.py
```

其他命令：

```bash
python infalsus_unlock.py info       # 查看当前剧情进度
python infalsus_unlock.py restore    # 用备份还原原始存档
python infalsus_unlock.py diag       # 存档布局异常时导出诊断信息
python infalsus_unlock.py patch "D:\path\to\savestate_V3.sav"   # 指定存档路径
python infalsus_unlock.py patch --yes    # 跳过确认提示（脚本化用）
python infalsus_unlock.py patch --force  # 已是解锁状态时强制重写
```

### 存档位置

工具会自动定位，无需手动查找。

| 平台 | 路径 |
|------|------|
| Windows | `%USERPROFILE%\AppData\LocalLow\lowiro\infalsus\<SteamID>\release\savestate_V3.sav` |
| macOS | `~/Library/Application Support/lowiro/infalsus/...` |
| Linux (Proton) | Steam compatdata 目录下的 `lowiro/infalsus/...` |

---

## 免责声明

- 本工具为**非官方粉丝作品**，与 lowiro 及《In Falsus》官方无关，未获任何官方背书或支持。
- 它只重写**本地存档**里的剧情进度表，**不修改游戏本体、不改内存、不联网上传任何内容**。
- 请使用**正版游戏**。
- 修改存档属于非官方手段。官方日后若加入存档校验或检测机制，可能导致存档异常、
  成就失效甚至账号受限。**由此产生的一切后果由使用者自行承担。**
- 本仓库**不包含任何游戏资源、受版权保护的内容或游戏文件**，只包含工具源码本身，
  以及一份纯数字的剧情段标识符列表。
- This is an unofficial, fan-made tool, not affiliated with lowiro. It only edits
  the local save file — no game files, no memory patching, no network access.
  Editing save data is unsupported; use at your own risk.

---

## 工作原理

《In Falsus》有 61 首歌靠推进 Scenario（剧情）解锁：游戏的 `RewardData` 资源记录了
「读完某段剧情 → 获得对应歌曲」的映射，而剧情本身是一条 236 个节点的链（读完 A 才能读 B）。

存档 `savestate_V3.sav` 用一个字典保存剧情进度，每条记录 20 字节。本工具重写这个字典，
把全部 236 段剧情标记为已读，从而让受剧情限制的歌曲在选曲界面出现。

存档中的其他数据（成绩、卡牌、设置）**逐字节原样保留**。

## 安全性

- **必须先退出游戏**。检测到 `infalsus.exe` 在运行时会直接中止，不做任何修改
  （否则游戏退出时会用内存里的存档覆盖改动）。
- 原始存档会**自动备份一次**为 `savestate_V3.sav.orig`，之后**永不覆盖**，
  因此 `restore` 一定能回到最初状态。
- 剧情表位置通过**模式匹配自动定位**，而非固定偏移，所以布局略有差异的存档也能正确处理。
- 如果 Steam Cloud 询问保留哪份存档，请选**本地 / 较新**的那份。

## 存档格式参考

```
offset 105121  0x02                    字典标记
offset 105122  int32                   条目数
offset 105126  条目 × 20 字节
     +0  int32  StoryIdentifier（剧情段 ID）
     +8  int32  MaxLineCountRead（已读行数）
     +12 byte   IsRead
     +13 byte   HasPlayedSongChallenge
     +14 byte   HasAllowedFastForwardSkipping
```

字段顺序与 IL2CPP 元数据中 `StoryEntryStateV5` 的定义一致。
偏移在不同存档之间会有浮动，因此工具采用自动定位。

## 自行构建 exe

仓库里已经带好了构建配置，直接用 spec 构建即可得到与 Release 一致的产物：

```bash
pip install pyinstaller
pyinstaller In_Falsus_unlocker.spec
```

或者手动指定参数：

```bash
pyinstaller --onefile --console --name In_Falsus_unlocker --icon icons/app.ico infalsus_unlock.py
```

> 打包出的单文件 exe 未做代码签名，部分杀毒软件可能误报，可从源码自行构建。

## 仓库结构

```
infalsus_unlock.py                 主工具（自包含，仅标准库）
In_Falsus_unlocker.spec            PyInstaller 构建配置
tools/export_reward_mapping.py     从游戏数据导出「剧情 → 歌曲」映射
tools/story_ids.json               236 个剧情段标识符
tools/falsus_save.py               早期调试用版本
icons/app.ico                      程序图标
```

## License

[MIT](LICENSE)
