# Huckleberry → HomePod 自动提醒

Mac 持续以只读方式获取 Huckleberry 的 SweetSpot 和喂奶提醒，到点后将中文语音通过 AirPlay 播放到单只 HomePod。

默认静默时段为晚上 21:00（含）至次日早上 08:00（不含）。静默期间到期的提醒在早上 08:00 后也不会补播，避免误报吵醒家人。
每次播报会使用 70% 音量，可通过 `.env` 中的 `HOMEPOD_VOLUME` 调整。

> Huckleberry 没有公开 API。本项目使用非官方的逆向客户端，可能因其后台更新而失效。项目不会向 Huckleberry 写入任何数据。

## 1. 安装

需要一台可长期运行的 Mac、一只与 Mac 位于同一网络的 HomePod，以及启用了 SweetSpot 的 Huckleberry 账户。

```bash
brew install uv
git clone https://github.com/Evann2026/huckleberry-homepod.git
cd ~/Projects/huckleberry-homepod
uv python install 3.14
uv sync
cp .env.example .env
```

打开 `.env`，填写：

- `HUCKLEBERRY_EMAIL` 和 `HUCKLEBERRY_PASSWORD`
- `BABY_NAME`：播报中使用的名字
- `TIMEZONE`：本地时区
- 其他时间、音量和静默时段可以按注释调整

`.env` 已被 Git 忽略，只保存在本机。不要提交、截图或分享这个文件。

## 2. 找到并测试 HomePod

确认 Mac 和 HomePod 在同一个网络。在“家庭”App 中，将“扬声器与电视访问权限”设为“同一网络中的任何人”。

```bash
uv run hb-homepod scan
```

从结果中找到 HomePod 的 `Identifier`，填入 `.env` 的 `HOMEPOD_ID`，然后测试：

```bash
uv run hb-homepod test-homepod
```

首次访问局域网时，macOS 可能要求授予“本地网络”权限。

## 3. 验证 Huckleberry 数据

先在 Huckleberry 中开启 SweetSpot Alert。睡眠固定采用每天 3 次小睡的 SweetSpot 方案。吃奶提醒读取上一次母乳或奶瓶记录，将其后 3 小时作为下一次吃奶时间。程序在第 2 小时 29 分进入待播报状态，以抵消最长约 1 分钟的轮询延迟；语音仍提示“还有 30 分钟”。

睡眠提醒同样提前补偿：预测时间前 16 分钟进入待播报状态，语音仍提示“15 分钟后进入最佳睡眠时间”。

```bash
# 只打印预测，不播报
DRY_RUN=1 uv run hb-homepod inspect

# 同步一次，并在提醒已到期时播报
uv run hb-homepod once

# 前台持续运行
uv run hb-homepod run
```

如果账户有多个孩子，请将目标资料的 ID 填入 `HUCKLEBERRY_CHILD_ID`；默认使用第一个资料。

## 4. 开机自动运行

完成前面三步后再安装后台服务：

```bash
chmod +x scripts/install-launch-agent.sh
./scripts/install-launch-agent.sh
```

日志位于 `~/Library/Logs/huckleberry-homepod/`。卸载：

```bash
launchctl bootout "gui/$(id -u)/com.local.huckleberry-homepod"
rm ~/Library/LaunchAgents/com.local.huckleberry-homepod.plist
```

## 保持 Mac 在线

显示器可以关闭，但 Mac 不能睡眠。在“系统设置 → 锁定屏幕/节能”中启用“显示器关闭时防止自动睡眠”，并保持 Mac 接通电源。
