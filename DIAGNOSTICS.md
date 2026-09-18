# App → Home 转场诊断包

## 身份与边界

- 基线：已合并并实机验证的 RandomFlip `0.0.8`。
- 本诊断版本：RootHide `0.0.9~diag1`。
- 用途：确认 iOS 15.4.1 与 iOS 16.0.3 上 App → Home 的真实 transaction、modifier、selector ABI 和完成/取消生命周期。
- 本包只观察系统对象并写入本地 plist；不修改系统动画、真实 App window、快照、frame、transform、alpha 或最终桌面状态。
- 本包不采集 App 包名、进程标识、触摸轨迹、用户输入或 App 画面。
- 与正式功能包严格区分：得到两台设备证据前，不启用“顶部磁吸收束”动画。

本包沿用 `com.tsangbaby.randomiconsflip`，安装时会替换现有 `0.0.8`，但保留原有图标动画。完成诊断后可重新安装 `0.0.8`，或等待后续正式 `0.0.9`。

## 输出文件

SpringBoard 每次启动时创建一个新诊断会话，并覆盖上一会话：

```text
/var/mobile/Library/Preferences/com.tsangbaby.randomiconsflip.transitiondiag.plist
```

plist 最多保留 128 个事件，权限设为 `0600`，并通过文件描述符设置 Protection Class C（首次解锁后可用）。为避免 pathname 重命名竞态，写入过程始终绑定最终文件的已验证 inode；它不承诺在进程异常终止时原子保留上一份会话，失败时只会删除仍指向该 inode 的不完整诊断文件。控制台日志统一使用：

```text
[RFAppToHomeDiag]
```

输出只包含：

- iOS 版本与 build；
- 候选类是否存在；
- selector 是否存在及其原始 type encoding；
- Hook 是否因签名检查而安装或跳过；
- transaction / modifier 的 begin、finish/end；
- `isGoingToLauncher` 与取消状态（仅接口存在且签名正确时）；
- 转场 context 动态类名、方向值；
- 主屏 bounds、scale、safe-area 上下边距；
- 是否竖屏、是否开启“减弱动态效果”。

## 每台设备的测试步骤

在 iOS 15.4.1 和 iOS 16.0.3 上分别执行：

1. 安装 `0.0.9~diag1` RootHide 包并注销或重启 SpringBoard。
2. 正常从桌面图标打开 App，再返回桌面。
3. 做一次 Home 手势并在中途取消。
4. 从文件夹打开 App，再返回桌面。
5. 从 App Library 打开 App，再返回桌面。
6. 从 Spotlight 打开 App，再返回桌面。
7. 开启“减弱动态效果”，再完成一次返回桌面，然后恢复原设置。
8. iOS 16.0.3：灵动岛无活动与有活动时各做一次正常返回。
9. 横屏 App 返回一次，用于确认诊断只记录方向、未来功能应回退原生。
10. 用 Filza 或终端导出上述 plist，文件名中注明系统版本，例如 `transitiondiag-ios15.4.1.plist`。

不要在两台设备之间复用同一个 plist；SpringBoard 重启会开始新会话并覆盖旧会话，所以完成一台设备的测试后应立即导出。
