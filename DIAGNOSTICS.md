# App → Home 转场诊断包

## 身份与边界

- 基线：已合并并实机验证的 RandomFlip `0.0.8`。
- 本诊断版本：RootHide `0.0.9~diag4`。
- 用途：确认 iOS 15.4.1 与 iOS 16.0.3 上 App → Home 的真实 transaction、modifier，以及 `frameForIndex:`、`scaleForIndex:`、`cornerRadiiForIndex:`、`layoutSettingsForTargetCenter:` 是否实际被调用。
- 本包只观察系统对象并写入本地 plist；不修改系统动画、真实 App window、快照、frame、transform、alpha 或最终桌面状态。
- 本包不采集 App 包名、进程标识、触摸轨迹、用户输入或 App 画面。
- 与正式功能包严格区分：得到两台设备证据前，不启用“顶部磁吸收束”动画。

本包沿用 `com.tsangbaby.randomiconsflip`，安装时会替换现有 `0.0.8`，但保留原有图标动画。完成诊断后可重新安装 `0.0.8`，或等待后续正式 `0.0.9`。

## 输出文件

`diag4` 沿用已验证的 tweak 专属真实用户数据目录：

```text
/var/mobile/Library/RandomIconsFlipDiagnostics/com.tsangbaby.randomiconsflip.transitiondiag.plist
```

同时始终尝试写一个只含固定阶段词的低级状态文件：

```text
/tmp/com.tsangbaby.randomiconsflip.transitiondiag.status.txt
```

状态文件只有 `schema`、`version`、`stage` 三项，不包含 App、进程、路径参数、对象描述、异常文本或用户数据。它通过 `/private/var/tmp` 的已验证目录 fd 和最终文件 fd 写入，权限为 `0600`。常见最终阶段包括：

- `plist-write-ok`：主 plist 已成功写入；
- `plist-directory-prepare-failed` / `plist-directory-validation-failed`：主目录准备或验证失败；
- `plist-file-open-failed` / `plist-file-validation-failed`：主文件打开或 inode 验证失败；
- `plist-protection-failed`：Protection Class C 设置或回读失败；
- `plist-data-write-failed` / `plist-final-validation-failed`：数据写入或最终校验失败；
- `startup-exception` / `writer-exception`：诊断启动或异步 writer 被异常边界拦截。

主 plist 每次 SpringBoard 启动创建新会话并覆盖上一会话，最多保留 128 个事件；每个 geometry hook 在整个 SpringBoard 生命周期内最多采样 8 条。文件权限设为 `0600`，并通过文件描述符设置 Protection Class C（首次解锁后可用）。为避免 pathname 重命名竞态，写入过程始终绑定最终文件的已验证 inode；它不承诺在进程异常终止时原子保留上一份会话，失败时只会删除仍指向该 inode 的不完整诊断文件。控制台日志统一使用：

```text
[RFAppToHomeDiag]
```

输出只包含：

- iOS 版本与 build；
- 候选类是否存在；
- selector 是否存在及其原始 type encoding；
- Hook 是否因签名检查而安装或跳过；
- transaction 的 begin/finish，以及 geometry selector 的实际调用；
- `isGoingToLauncher` 与取消状态（仅接口存在且签名正确时）；
- 转场 context 动态类名、原始方向值、方向是否已知，以及 context/Scene 选出的有效方向；
- 主屏 bounds、scale、safe-area 上下边距；
- 是否竖屏、是否开启“减弱动态效果”；
- geometry hook 的固定名称、索引，以及系统原方法返回的 frame、scale、四角半径或 target center；对象返回只记录是否为空。

## 两台设备的最小测试步骤

`diag1`–`diag3` 已闭合两台设备的 inventory、写入路径和 transaction 证据；`diag4` 只确认真实 modifier/geometry 调用。请在 iOS 15.4.1 与 iOS 16.0.3 上各做一次以下步骤，不需要练习取消手势：

1. 安装 `0.0.9~diag4` RootHide 包并注销或重启 SpringBoard 一次。
2. 确认原有桌面图标随机动画仍正常。
3. 打开任意普通竖屏 App，再正常返回桌面一次。
4. 等待约 3 秒，让异步 writer 完成；用 Filza 查看主 plist 路径，若文件存在，直接发送该 plist。
5. 若主 plist 仍不存在，直接转到 `/tmp`，发送 `com.tsangbaby.randomiconsflip.transitiondiag.status.txt`。

不需要运行终端命令，不需要重复安装，也不需要再次尝试中途取消 Home 手势。主 plist 和状态文件都会被后续启动/写入覆盖，因此完成后应直接导出当前文件。
