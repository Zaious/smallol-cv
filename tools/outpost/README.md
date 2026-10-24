# Outpost 上的排程（root 安裝一次）

```bash
cp tools/outpost/smallol-*.service tools/outpost/smallol-*.timer /etc/systemd/system/
mkdir -p /etc/systemd/system/apt-daily-upgrade.timer.d
cp tools/outpost/apt-daily-upgrade.override.conf /etc/systemd/system/apt-daily-upgrade.timer.d/override.conf
systemctl daemon-reload
systemctl enable --now smallol-watchdog.timer smallol-daily.timer
```

- `smallol-watchdog`：每分鐘，卡住的程序自己重啟（tools/watchdog.py）。
- `smallol-daily`：每天 09:00 UTC，更新 yt-dlp、刪 7 天前的轉播畫面（daily.sh）。
- 系統自動更新固定在 09:30–10:00 UTC。
- 手動重啟一律用 `tools/safe_restart.sh service|feed|watch`（先過 tools/deploy_gate.py：BP 中、開賽前 10 分鐘不准）。
