# Random Icon Flip — Swift 重构版

这是由 tsangbaby 维护的 `RandomFlip` Swift 现代化重构版。核心行为是：在桌面空闲时，随机选择一个当前可见的主屏幕或 Dock 图标，执行翻转、弹跳、角度摇摆、轻旋转、水平震动、跳起落地、果冻挤压、轨道螺旋、Flutter / Leaf 风吹叶片、Infinity Drift / Figure Eight（∞ 漂移 / 8 字巡航）、Rocket Launch（火箭升空）或 Slingshot（弹弓弹射）动画。

## 当前交付状态

- 源码交付：完成
- 最低部署版本：iOS 15.0
- 架构：Swift 核心 + 极小 Logos 启动 Hook
- 注入范围：仅 `com.apple.springboard`
- 当前候选版本：RootHide `0.1.0`
- Debian 包标识符：`com.tsangbaby.randomiconsflip`
- Rootless / RootHide：项目结构预留，可由现代 Theos scheme 构建
- 编译方式：由 GitHub Actions `macos-14` 云端构建
- 实机验证：`0.0.8` 是当前实机验证基线；`0.1.0` 的 Rocket Launch / Slingshot 尚待实机验证

源码合同、云端构建和包级验证是不同证据；不能仅凭源码合同表述为“已生成测试包”，也不能仅凭构建成功表述为“已在 iOS 15+ 实机验证”。

## 与原版相比

保留：

- 随机图标；
- 左/右随机翻转；
- 0.5–1.4 秒动画时长；
- 0.50–4.09 秒随机尝试间隔；
- 桌面可见时才工作。

现代化：

- 调度、状态和动画逻辑全部迁移到 Swift；
- 使用 `Int.random(in:)`，移除错误的 `rand()/srand()` 用法；
- 修复原版随机索引可能越界和空数组取模风险；
- 使用 `DispatchWorkItem` 管理可取消的一次性调度；
- 使用 `UIView.transition` 代替已淘汰的 `beginAnimations/commitAnimations`；
- 尊重“减弱动态效果”；
- 搜索、滚动、编辑、文件夹打开/转换、Home 状态转换、全局图标拖拽和上下文菜单期间安全跳过；
- 启动后及任何不安全状态结束后，必须连续两次通过完整 readiness 检查才开始翻转；固定 1.5 秒只负责首次尝试，不作为桌面就绪证明；
- 不主动移除 SpringBoard 图层动画，也不在 UIKit completion 到达前释放本次翻转状态；
- 私有 API 全部在运行时查找并校验零参数/返回 ABI；任何关键安全接口缺失或签名不符时，本次动画直接停用。

## iOS 15+ 兼容策略

固定提交的 iOS 15.5、iOS 17 与 iOS 18 beta SpringBoard 头文件均包含本实现依赖的核心调用面：

- `SpringBoard -applicationDidFinishLaunching:`
- `SpringBoard -isShowingHomescreen`
- `SBIconController +sharedInstance/+sharedInstanceIfExists`
- `SBIconController -iconManager`
- `SBIconController -areHomeScreenIconsOccluded`
- `SBHIconManager -hasOpenFolder/-isScrolling/-isEditing`
- `SBIconView -_iconImageView/-isGrabbed`

实现不直接链接这些私有类，而是逐个检查类与 selector。iOS 15 是明确部署下限；更高版本在上述运行时接口仍存在时继续工作。未来系统若移除关键接口，插件会停止动画而不是调用未知 ABI。任何尚未实机测试的未来版本都不能仅凭此策略宣称完全兼容。

## 项目结构

```text
RandomFlip-Swift/
├── Makefile
├── control
├── RandomIconsFlip.plist
├── RandomIconsFlip-Bridging-Header.h
├── RuntimeBridge.m
├── Tweak.xm
├── Sources/
│   ├── RandomFlipManager.swift
│   └── SpringBoardEnvironment.swift
├── tests/
│   └── test_source_contract.py
├── NOTICE.md
└── README.md
```

`Tweak.xm` 只 Hook SpringBoard 启动方法并调用 Swift 单例。`RuntimeBridge.m` 只负责类型安全的 Objective-C runtime 消息边界。功能逻辑位于两份 Swift 文件中。

## 构建方式

需要现代 Theos、支持 iOS 交叉编译的 Swift 工具链及 iPhoneOS SDK。准备好环境后：

```sh
# RootHide
make clean package FINALPACKAGE=1 PACKAGE_VERSION=0.1.0 THEOS_PACKAGE_SCHEME=roothide
```

构建前应先确认所用 Theos 版本确实包含 RootHide scheme，并使用至少 iOS 15 SDK。不要把通过 Python 源码合同等同于 Swift 编译成功。

## 验证

源码合同：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -p 'test_*.py' -v
```

`0.0.8` 是当前实机验证基线。`0.1.0` 需完成本轮 RootHide 构建与包级验证后，再在 iOS 15、16 上测试 Rocket Launch / Slingshot，以及桌面、Dock、翻页、搜索、文件夹、抖动编辑、拖拽、锁屏/解锁和减少动态效果。

## 署名与许可边界

本重构由 tsangbaby 维护和署名。原始压缩包的 README 写明项目为 open source，但压缩包中没有明确的 `LICENSE` 文件；本项目不替任何来源方推定或新增许可证。公开分发前请确认原项目许可条件，详见 `NOTICE.md`。
