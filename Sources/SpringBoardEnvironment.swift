import UIKit

@MainActor
final class SpringBoardEnvironment {
    private let application: UIApplication

    init(application: UIApplication = .shared) {
        self.application = application
    }

    func randomAnimationTarget() -> UIView? {
        precondition(Thread.isMainThread)

        guard isSafeToAnimateHomeScreen() else {
            return nil
        }

        return visibleIconViews()
            .compactMap { animationView(for: $0) }
            .randomElement()
    }

    private func isSafeToAnimateHomeScreen() -> Bool {
        guard readBool(application, selector: "isShowingHomescreen") == true,
              let iconController = RFSharedInstanceForClassNamed("SBIconController"),
              requiredFalse(iconController, selectors: [
                "areHomeScreenIconsOccluded",
                "areAnyIconViewContextMenusAnimating",
                "areAnyIconViewContextMenusShowing",
                "isShowingHomeScreenOverlay",
                "isShowingSidebar"
              ]),
              let iconManager = RFInvokeObjectSelector(iconController, "iconManager"),
              requiredFalse(iconManager, selectors: [
                "hasOpenFolder",
                "hasAnimatingFolder",
                "isTransitioning",
                "isTransitioningHomeScreenState",
                "isScrolling",
                "isEditing",
                "isShowingPullDownSearchOrTransitioningToVisible",
                "isIconDragging",
                "isShowingIconContextMenu"
              ]) else {
            return false
        }

        return true
    }

    private func readBool(_ object: Any, selector: String) -> Bool? {
        return RFReadBoolSelector(object, selector)?.boolValue
    }

    private func requiredFalse(_ object: Any, selectors: [String]) -> Bool {
        for selector in selectors {
            guard let value = readBool(object, selector: selector), !value else {
                return false
            }
        }
        return true
    }

    private func visibleIconViews() -> [UIView] {
        guard let iconViewClass = NSClassFromString("SBIconView") else {
            return []
        }

        var stack = foregroundWindows().flatMap { $0.subviews }
        var results: [UIView] = []
        var seen = Set<ObjectIdentifier>()

        while let view = stack.popLast() {
            guard !view.isHidden, view.alpha > 0.01 else {
                continue
            }

            stack.append(contentsOf: view.subviews)

            guard view.isKind(of: iconViewClass),
                  isEffectivelyVisible(view),
                  belongsToRootOrDock(view),
                  !isIconBusy(view) else {
                continue
            }

            let identifier = ObjectIdentifier(view)
            if seen.insert(identifier).inserted {
                results.append(view)
            }
        }

        return results
    }

    private func belongsToRootOrDock(_ iconView: UIView) -> Bool {
        guard let iconListViewClass = NSClassFromString("SBIconListView"),
              let iconListView = firstAncestor(of: iconView, matching: iconListViewClass),
              readBool(iconListView, selector: "isTransitioningIconLocation") == false else {
            return false
        }

        if readBool(iconListView, selector: "isDock") == true {
            return true
        }

        guard let location = RFInvokeObjectSelector(iconListView, "iconLocation") as? String else {
            return false
        }

        return location == "SBIconLocationRoot" || location == "SBIconLocationDock"
    }

    private func firstAncestor(of view: UIView, matching targetClass: AnyClass) -> UIView? {
        var ancestor = view.superview

        while let current = ancestor {
            if current.isKind(of: targetClass) {
                return current
            }
            ancestor = current.superview
        }

        return nil
    }

    private func foregroundWindows() -> [UIWindow] {
        return application.connectedScenes
            .compactMap { $0 as? UIWindowScene }
            .filter { $0.activationState == .foregroundActive }
            .flatMap { $0.windows }
            .filter {
                !$0.isHidden &&
                $0.alpha > 0.01 &&
                $0.screen === UIScreen.main
            }
    }

    private func isEffectivelyVisible(_ view: UIView) -> Bool {
        guard let window = view.window,
              !view.bounds.isEmpty else {
            return false
        }

        var ancestor: UIView? = view
        while let current = ancestor {
            if current.isHidden || current.alpha <= 0.01 {
                return false
            }
            if current === window {
                break
            }
            ancestor = current.superview
        }

        let frameInWindow = view.convert(view.bounds, to: window)
        guard !frameInWindow.isEmpty,
              !frameInWindow.isNull,
              !frameInWindow.isInfinite else {
            return false
        }

        return frameInWindow.intersects(window.bounds)
    }

    private func isIconBusy(_ iconView: UIView) -> Bool {
        return !requiredFalse(iconView, selectors: [
            "isGrabbed",
            "isDragging",
            "isDragLifted",
            "isEditing",
            "isAnimatingScrolling",
            "isContextMenuInteractionActive"
        ])
    }

    private func animationView(for iconView: UIView) -> UIView? {
        if let imageView = RFInvokeObjectSelector(iconView, "_iconImageView") as? UIView,
           isEffectivelyVisible(imageView) {
            return imageView
        }

        if let imageViewClass = NSClassFromString("SBIconImageView"),
           let imageView = firstDescendant(of: iconView, matching: imageViewClass),
           isEffectivelyVisible(imageView) {
            return imageView
        }

        return nil
    }

    private func firstDescendant(of rootView: UIView, matching targetClass: AnyClass) -> UIView? {
        var stack = rootView.subviews

        while let view = stack.popLast() {
            if view.isKind(of: targetClass) {
                return view
            }
            stack.append(contentsOf: view.subviews)
        }

        return nil
    }
}
