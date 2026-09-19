from __future__ import annotations

import plistlib
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class RandomFlipSwiftSourceContract(unittest.TestCase):
    def test_swift_core_with_one_minimal_logos_entry(self) -> None:
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        hook = (ROOT / "Tweak.xm").read_text(encoding="utf-8")
        manager = (ROOT / "Sources" / "RandomFlipManager.swift").read_text(encoding="utf-8")
        environment = (ROOT / "Sources" / "SpringBoardEnvironment.swift").read_text(encoding="utf-8")

        self.assertIn("TARGET = iphone:clang:latest:15.0", makefile)
        self.assertIn("Sources/RandomFlipManager.swift", makefile)
        self.assertIn("Sources/SpringBoardEnvironment.swift", makefile)
        self.assertEqual(hook.count("%hook"), 1)
        self.assertIn("%hook SpringBoard", hook)
        self.assertIn("applicationDidFinishLaunching:", hook)
        self.assertIn("<RandomIconsFlip-Swift.h>", hook)

        self.assertIn("final class RandomFlipManager", manager)
        self.assertIn("DispatchWorkItem", manager)
        self.assertIn("UIView.transition", manager)
        self.assertIn("Int.random(in: 50...409)", manager)
        self.assertIn("Int.random(in: 5...14)", manager)
        self.assertIn("UIAccessibility.isReduceMotionEnabled", manager)

        self.assertIn('"isShowingHomescreen"', environment)
        self.assertIn('"areHomeScreenIconsOccluded"', environment)
        self.assertIn('"hasOpenFolder"', environment)
        self.assertIn('"isScrolling"', environment)
        self.assertIn('"isEditing"', environment)
        self.assertIn('NSClassFromString("SBIconView")', environment)
        self.assertIn('NSClassFromString("SBIconListView")', environment)
        self.assertIn('"SBIconLocationRoot"', environment)
        self.assertIn('"SBIconLocationDock"', environment)
        self.assertIn('"isTransitioningIconLocation"', environment)
        self.assertIn('"_iconImageView"', environment)

        combined = hook + manager + environment
        for legacy in ("rand()", "srand(", "beginAnimations", "commitAnimations", "performSelector"):
            self.assertNotIn(legacy, combined)

    def test_runtime_safety_gates_fail_closed(self) -> None:
        header = (ROOT / "RandomIconsFlip-Bridging-Header.h").read_text(encoding="utf-8")
        bridge = (ROOT / "RuntimeBridge.m").read_text(encoding="utf-8")
        manager = (ROOT / "Sources" / "RandomFlipManager.swift").read_text(encoding="utf-8")
        environment = (ROOT / "Sources" / "SpringBoardEnvironment.swift").read_text(encoding="utf-8")

        self.assertIn("#pragma once", header)
        self.assertIn("RFReadBoolSelector", header)
        self.assertIn("methodSignatureForSelector", bridge)
        self.assertIn("RFReadBoolSelector", environment)
        for selector in (
            "isShowingPullDownSearchOrTransitioningToVisible",
            "isIconDragging",
            "hasAnimatingFolder",
            "isTransitioning",
            "isTransitioningHomeScreenState",
            "isShowingIconContextMenu",
        ):
            self.assertIn(f'"{selector}"', environment)

        self.assertIn(
            'let iconManager = RFInvokeObjectSelector(iconController, "iconManager")',
            environment,
        )
        self.assertIn("requiredFalse", environment)
        self.assertNotIn("RFInvokeBoolSelector", environment)
        self.assertNotIn("return isEffectivelyVisible(iconView) ? iconView : nil", environment)
        self.assertNotIn("animationWatchdogMargin", manager)
        self.assertNotIn("removeAllAnimations", manager)
        self.assertIn("requiredConsecutiveReadyTicks = 2", manager)
        self.assertIn("consecutiveReadyTicks", manager)
        self.assertIn("consecutiveReadyTicks = 0", manager)
        self.assertGreaterEqual((manager + environment).count("@MainActor"), 2)

    def test_random_animation_pool_uses_twelve_transform_safe_styles(self) -> None:
        manager = (ROOT / "Sources" / "RandomFlipManager.swift").read_text(encoding="utf-8")

        for style in (
            "flip",
            "bounce",
            "wiggle",
            "rotation",
            "horizontalShake",
            "jumpLanding",
            "jelly",
            "orbitSpiral",
            "flutterLeaf",
            "infinityDrift",
            "rocketLaunch",
            "slingshot",
        ):
            self.assertIn(f"case {style}", manager)

        pool = re.search(
            r"private static let animationPool: \[IconAnimationStyle\] = \[(.*?)\]",
            manager,
            re.DOTALL,
        )
        self.assertIsNotNone(pool)
        assert pool is not None
        styles = re.findall(
            r"\.(flip|bounce|wiggle|rotation|horizontalShake|jumpLanding|jelly|orbitSpiral|flutterLeaf|infinityDrift|rocketLaunch|slingshot)",
            pool.group(1),
        )
        self.assertCountEqual(
            styles,
            [
                "flip",
                "bounce", "bounce",
                "wiggle", "wiggle",
                "rotation", "rotation",
                "horizontalShake", "horizontalShake",
                "jumpLanding", "jumpLanding",
                "jelly", "jelly",
                "orbitSpiral", "orbitSpiral",
                "flutterLeaf", "flutterLeaf",
                "infinityDrift", "infinityDrift",
                "rocketLaunch", "rocketLaunch",
                "slingshot", "slingshot",
            ],
        )
        self.assertEqual(styles.count("flip"), 1)
        for style in (
            "bounce",
            "wiggle",
            "rotation",
            "horizontalShake",
            "jumpLanding",
            "jelly",
            "orbitSpiral",
            "flutterLeaf",
            "infinityDrift",
            "rocketLaunch",
            "slingshot",
        ):
            self.assertEqual(styles.count(style), 2)
        self.assertIn("Self.animationPool.randomElement() ?? .flip", manager)

        for helper in (
            "animateFlip",
            "animateBounce",
            "animateWiggle",
            "animateRotation",
            "animateHorizontalShake",
            "animateJumpLanding",
            "animateJelly",
            "animateOrbitSpiral",
            "animateFlutterLeaf",
            "animateInfinityDrift",
            "animateRocketLaunch",
            "animateSlingshot",
        ):
            self.assertIn(f"private func {helper}", manager)
        self.assertIn("UIView.animateKeyframes", manager)
        self.assertGreaterEqual(manager.count("let baseTransform = view.transform"), 11)
        self.assertIn("baseTransform.scaledBy", manager)
        self.assertIn("baseTransform.rotated(by:", manager)
        self.assertGreaterEqual(manager.count("view.transform = baseTransform"), 3)
        self.assertIn(".beginFromCurrentState", manager)
        self.assertIn(".allowUserInteraction", manager)
        self.assertNotIn("view.frame =", manager)
        self.assertNotIn("view.center =", manager)
        self.assertNotIn("removeAllAnimations", manager)

    def test_animation_amplitudes_are_more_visible_but_bounded(self) -> None:
        manager = (ROOT / "Sources" / "RandomFlipManager.swift").read_text(encoding="utf-8")

        for expected in (
            "baseTransform.scaledBy(x: 0.74, y: 0.74)",
            "baseTransform.scaledBy(x: 1.20, y: 1.20)",
            "baseTransform.scaledBy(x: 0.94, y: 0.94)",
            "let angle = CGFloat.pi / 12.0",
            "let angle = direction * CGFloat.pi / 6.0",
            ".scaledBy(x: 1.08, y: 1.08)",
        ):
            self.assertIn(expected, manager)

        for superseded in (
            "baseTransform.scaledBy(x: 0.86, y: 0.86)",
            "baseTransform.scaledBy(x: 1.10, y: 1.10)",
            "baseTransform.scaledBy(x: 0.97, y: 0.97)",
            "let angle = CGFloat.pi / 24.0",
            "let angle = direction * CGFloat.pi / 10.0",
            ".scaledBy(x: 1.04, y: 1.04)",
        ):
            self.assertNotIn(superseded, manager)

        self.assertIn("view.transform = baseTransform", manager)
        self.assertNotIn("view.frame =", manager)
        self.assertNotIn("view.center =", manager)

    def test_horizontal_shake_translates_and_restores_the_icon_image(self) -> None:
        manager = (ROOT / "Sources" / "RandomFlipManager.swift").read_text(encoding="utf-8")

        self.assertIn("case horizontalShake", manager)
        pool = re.search(
            r"private static let animationPool: \[IconAnimationStyle\] = \[(.*?)\]",
            manager,
            re.DOTALL,
        )
        self.assertIsNotNone(pool)
        self.assertEqual(pool.group(1).count(".horizontalShake"), 2)
        self.assertIn("case .horizontalShake:", manager)
        self.assertIn("animateHorizontalShake(on: view, duration: duration, completion: completion)", manager)
        self.assertIn("private func animateHorizontalShake", manager)
        self.assertIn("let horizontalOffset: CGFloat = 10.0", manager)
        self.assertIn("baseTransform.translatedBy(x: horizontalOffset, y: 0)", manager)
        self.assertIn("baseTransform.translatedBy(x: -horizontalOffset, y: 0)", manager)
        self.assertIn("baseTransform.translatedBy(x: horizontalOffset * 0.70, y: 0)", manager)
        self.assertIn("baseTransform.translatedBy(x: -horizontalOffset * 0.45, y: 0)", manager)
        self.assertIn("view.transform = baseTransform", manager)
        self.assertNotIn("view.frame =", manager)
        self.assertNotIn("view.center =", manager)
        self.assertNotIn("removeAllAnimations", manager)

    def test_jump_landing_moves_vertically_and_restores_the_icon_image(self) -> None:
        manager = (ROOT / "Sources" / "RandomFlipManager.swift").read_text(encoding="utf-8")

        self.assertIn("case jumpLanding", manager)
        pool = re.search(
            r"private static let animationPool: \[IconAnimationStyle\] = \[(.*?)\]",
            manager,
            re.DOTALL,
        )
        self.assertIsNotNone(pool)
        self.assertEqual(pool.group(1).count(".jumpLanding"), 2)
        self.assertIn("case .jumpLanding:", manager)
        self.assertIn("animateJumpLanding(on: view, duration: duration, completion: completion)", manager)
        self.assertIn("private func animateJumpLanding", manager)
        self.assertIn("let jumpHeight: CGFloat = 12.0", manager)
        self.assertIn("let landingDepth: CGFloat = 3.0", manager)
        self.assertIn("baseTransform.translatedBy(x: 0, y: -jumpHeight)", manager)
        self.assertIn(".scaledBy(x: 1.08, y: 1.08)", manager)
        self.assertIn("baseTransform.translatedBy(x: 0, y: landingDepth)", manager)
        self.assertIn(".scaledBy(x: 1.10, y: 0.88)", manager)
        self.assertIn("view.transform = baseTransform", manager)
        self.assertNotIn("view.frame =", manager)
        self.assertNotIn("view.center =", manager)
        self.assertNotIn("removeAllAnimations", manager)

    def test_jelly_squash_uses_nonuniform_scaling_and_restores_the_icon_image(self) -> None:
        manager = (ROOT / "Sources" / "RandomFlipManager.swift").read_text(encoding="utf-8")

        self.assertIn("case jelly", manager)
        pool = re.search(
            r"private static let animationPool: \[IconAnimationStyle\] = \[(.*?)\]",
            manager,
            re.DOTALL,
        )
        self.assertIsNotNone(pool)
        self.assertEqual(pool.group(1).count(".jelly"), 2)
        self.assertIn("case .jelly:", manager)
        self.assertIn("animateJelly(on: view, duration: duration, completion: completion)", manager)
        self.assertIn("private func animateJelly", manager)
        self.assertIn("baseTransform.scaledBy(x: 1.16, y: 0.84)", manager)
        self.assertIn("baseTransform.scaledBy(x: 0.88, y: 1.14)", manager)
        self.assertIn("baseTransform.scaledBy(x: 1.06, y: 0.95)", manager)
        self.assertIn("view.transform = baseTransform", manager)
        self.assertNotIn("view.frame =", manager)
        self.assertNotIn("view.center =", manager)
        self.assertNotIn("view.alpha =", manager)
        self.assertNotIn("removeAllAnimations", manager)

    def test_orbit_spiral_has_noticeable_transform_path_and_restores_the_icon_image(self) -> None:
        manager = (ROOT / "Sources" / "RandomFlipManager.swift").read_text(encoding="utf-8")

        self.assertIn("case orbitSpiral", manager)
        pool = re.search(
            r"private static let animationPool: \[IconAnimationStyle\] = \[(.*?)\]",
            manager,
            re.DOTALL,
        )
        self.assertIsNotNone(pool)
        assert pool is not None
        self.assertEqual(pool.group(1).count(".orbitSpiral"), 2)
        self.assertIn("case .orbitSpiral:", manager)
        self.assertIn("animateOrbitSpiral(on: view, duration: duration, completion: completion)", manager)
        self.assertIn("private func animateOrbitSpiral", manager)
        self.assertIn("let orbitRadiusX: CGFloat = 16.0", manager)
        self.assertIn("let orbitRadiusY: CGFloat = 13.0", manager)
        self.assertIn("let orbitAngle = CGFloat.pi / 7.0", manager)
        self.assertRegex(
            manager,
            r"baseTransform\s*\.translatedBy\(x:\s*orbitRadiusX,\s*y:\s*-orbitRadiusY\)",
        )
        self.assertRegex(
            manager,
            r"baseTransform\s*\.translatedBy\(x:\s*-orbitRadiusX,\s*y:\s*orbitRadiusY\)",
        )
        self.assertIn(".rotated(by: orbitAngle)", manager)
        self.assertIn(".scaledBy(x: 1.10, y: 1.10)", manager)
        self.assertIn("view.transform = baseTransform", manager)
        self.assertNotIn("view.frame =", manager)
        self.assertNotIn("view.center =", manager)
        self.assertNotIn("layer.transform", manager)
        self.assertNotIn("removeAllAnimations", manager)

    def test_flutter_leaf_has_visible_sway_path_and_restores_the_icon_image(self) -> None:
        manager = (ROOT / "Sources" / "RandomFlipManager.swift").read_text(encoding="utf-8")

        self.assertIn("case flutterLeaf", manager)
        pool = re.search(
            r"private static let animationPool: \[IconAnimationStyle\] = \[(.*?)\]",
            manager,
            re.DOTALL,
        )
        self.assertIsNotNone(pool)
        assert pool is not None
        self.assertEqual(pool.group(1).count(".flutterLeaf"), 2)
        self.assertIn("case .flutterLeaf:", manager)
        self.assertIn("animateFlutterLeaf(on: view, duration: duration, completion: completion)", manager)
        self.assertIn("private func animateFlutterLeaf", manager)
        self.assertIn("let leafOffsetX: CGFloat = 12.0", manager)
        self.assertIn("let leafOffsetY: CGFloat = 8.0", manager)
        self.assertIn("let leafAngle = CGFloat.pi / 10.0", manager)
        self.assertRegex(
            manager,
            r"baseTransform\s*\.translatedBy\(x:\s*-leafOffsetX,\s*y:\s*-leafOffsetY",
        )
        self.assertRegex(
            manager,
            r"baseTransform\s*\.translatedBy\(x:\s*leafOffsetX,\s*y:\s*leafOffsetY",
        )
        self.assertIn(".rotated(by: -leafAngle)", manager)
        self.assertIn(".rotated(by: leafAngle)", manager)
        self.assertIn(".scaledBy(x: 1.06, y: 0.95)", manager)
        self.assertIn(".scaledBy(x: 0.96, y: 1.04)", manager)
        self.assertIn("view.transform = baseTransform", manager)
        self.assertNotIn("view.frame =", manager)
        self.assertNotIn("view.center =", manager)
        self.assertNotIn("layer.transform", manager)
        self.assertNotIn("removeAllAnimations", manager)

    def test_infinity_drift_traces_a_bounded_figure_eight_and_restores_the_icon_image(self) -> None:
        manager = (ROOT / "Sources" / "RandomFlipManager.swift").read_text(encoding="utf-8")

        self.assertIn("case infinityDrift", manager)
        pool = re.search(
            r"private static let animationPool: \[IconAnimationStyle\] = \[(.*?)\]",
            manager,
            re.DOTALL,
        )
        self.assertIsNotNone(pool)
        assert pool is not None
        self.assertEqual(pool.group(1).count(".infinityDrift"), 2)
        self.assertIn("case .infinityDrift:", manager)
        self.assertIn("animateInfinityDrift(on: view, duration: duration, completion: completion)", manager)

        method = re.search(
            r"private func animateInfinityDrift\((.*?)\n    }\n\n    private func animateRocketLaunch",
            manager,
            re.DOTALL,
        )
        self.assertIsNotNone(method)
        assert method is not None
        body = method.group(1)

        self.assertIn("let infinityOffsetX: CGFloat = 14.0", body)
        self.assertIn("let infinityOffsetY: CGFloat = 8.0", body)
        self.assertIn("withDuration: min(duration, 0.95)", body)
        for expected in (
            "translatedBy(x: infinityOffsetX * 0.72, y: -infinityOffsetY)",
            "translatedBy(x: infinityOffsetX, y: 0)",
            "translatedBy(x: infinityOffsetX * 0.72, y: infinityOffsetY)",
            "translatedBy(x: -infinityOffsetX * 0.72, y: -infinityOffsetY)",
            "translatedBy(x: -infinityOffsetX, y: 0)",
            "translatedBy(x: -infinityOffsetX * 0.72, y: infinityOffsetY)",
        ):
            self.assertIn(expected, body)
        keyframes = re.findall(
            r"withRelativeStartTime: ([0-9.]+), relativeDuration: ([0-9.]+)",
            body,
        )
        self.assertEqual(
            keyframes,
            [
                ("0.000", "0.125"),
                ("0.125", "0.125"),
                ("0.250", "0.125"),
                ("0.375", "0.125"),
                ("0.500", "0.125"),
                ("0.625", "0.125"),
                ("0.750", "0.125"),
                ("0.875", "0.125"),
            ],
        )
        keyframe_restores = re.findall(
            r"view\.transform = baseTransform\n\s*}",
            body,
        )
        self.assertEqual(len(keyframe_restores), 2)
        self.assertIn(
            "} completion: { finished in\n            view.transform = baseTransform",
            body,
        )
        self.assertNotIn(".rotated(by:", body)
        self.assertNotIn(".scaledBy(", body)
        self.assertNotIn("view.frame =", body)
        self.assertNotIn("view.center =", body)
        self.assertNotIn("view.alpha =", body)
        self.assertNotIn("layer.transform", body)
        self.assertNotIn("removeAllAnimations", body)

    def test_rocket_launch_has_bounded_takeoff_landing_and_restores_transform(self) -> None:
        manager = (ROOT / "Sources" / "RandomFlipManager.swift").read_text(encoding="utf-8")

        self.assertIn("case rocketLaunch", manager)
        pool = re.search(
            r"private static let animationPool: \[IconAnimationStyle\] = \[(.*?)\]",
            manager,
            re.DOTALL,
        )
        self.assertIsNotNone(pool)
        assert pool is not None
        self.assertEqual(pool.group(1).count(".rocketLaunch"), 2)
        self.assertIn("case .rocketLaunch:", manager)
        self.assertIn("animateRocketLaunch(on: view, duration: duration, completion: completion)", manager)

        method = re.search(
            r"private func animateRocketLaunch\((.*?)\n    }\n\n    private func animateSlingshot",
            manager,
            re.DOTALL,
        )
        self.assertIsNotNone(method)
        assert method is not None
        body = method.group(1)
        for expected in (
            "let baseTransform = view.transform",
            "let launchHeight: CGFloat = 30.0",
            "let landingDepth: CGFloat = 5.0",
            "CGFloat.pi / 18.0",
            "withDuration: min(duration, 1.05)",
            ".translatedBy(x: 0, y: -launchHeight)",
            ".translatedBy(x: 0, y: landingDepth)",
            ".scaledBy(x: 1.28, y: 0.72)",
            "view.transform = baseTransform",
            "completion(finished)",
        ):
            self.assertIn(expected, body)
        self.assertEqual(
            re.findall(
                r"withRelativeStartTime: ([0-9.]+), relativeDuration: ([0-9.]+)",
                body,
            ),
            [
                ("0.00", "0.14"),
                ("0.14", "0.26"),
                ("0.40", "0.22"),
                ("0.62", "0.18"),
                ("0.80", "0.12"),
                ("0.92", "0.08"),
            ],
        )
        self.assertNotIn("view.frame =", body)
        self.assertNotIn("view.center =", body)
        self.assertNotIn("view.alpha =", body)
        self.assertNotIn("removeAllAnimations", body)

    def test_slingshot_has_four_directional_paths_and_restores_transform(self) -> None:
        manager = (ROOT / "Sources" / "RandomFlipManager.swift").read_text(encoding="utf-8")

        self.assertIn("case slingshot", manager)
        pool = re.search(
            r"private static let animationPool: \[IconAnimationStyle\] = \[(.*?)\]",
            manager,
            re.DOTALL,
        )
        self.assertIsNotNone(pool)
        assert pool is not None
        self.assertEqual(pool.group(1).count(".slingshot"), 2)
        self.assertIn("case .slingshot:", manager)
        self.assertIn("animateSlingshot(on: view, duration: duration, completion: completion)", manager)

        method = re.search(
            r"private func animateSlingshot\((.*?)\n    }\n\n    private func finishAnimation",
            manager,
            re.DOTALL,
        )
        self.assertIsNotNone(method)
        assert method is not None
        body = method.group(1)
        for expected in (
            "let baseTransform = view.transform",
            "let direction: CGFloat = Bool.random() ? 1.0 : -1.0",
            "let verticalDirection: CGFloat = Bool.random() ? 1.0 : -1.0",
            "let slingshotOffsetX: CGFloat = 30.0",
            "let slingshotOffsetY: CGFloat = 14.0",
            "let slingshotAngle = direction * CGFloat.pi / 5.0",
            "withDuration: min(duration, 1.00)",
            "x: direction * slingshotOffsetX",
            "y: verticalDirection * slingshotOffsetY",
            ".rotated(by: slingshotAngle)",
            ".scaledBy(x: 1.18, y: 0.86)",
            "view.transform = baseTransform",
            "completion(finished)",
        ):
            self.assertIn(expected, body)
        self.assertEqual(
            re.findall(
                r"withRelativeStartTime: ([0-9.]+), relativeDuration: ([0-9.]+)",
                body,
            ),
            [
                ("0.00", "0.16"),
                ("0.16", "0.30"),
                ("0.46", "0.22"),
                ("0.68", "0.17"),
                ("0.85", "0.15"),
            ],
        )
        self.assertNotIn("view.frame =", body)
        self.assertNotIn("view.center =", body)
        self.assertNotIn("view.alpha =", body)
        self.assertNotIn("removeAllAnimations", body)

    def test_displayed_icon_discovery_includes_generic_floating_docks(self) -> None:
        header = (ROOT / "RandomIconsFlip-Bridging-Header.h").read_text(encoding="utf-8")
        bridge = (ROOT / "RuntimeBridge.m").read_text(encoding="utf-8")
        environment = (ROOT / "Sources" / "SpringBoardEnvironment.swift").read_text(encoding="utf-8")

        self.assertIn("RFDisplayedIconViews", header)
        self.assertIn("RFDisplayedIconViews", bridge)
        self.assertIn('NSSelectorFromString(@"enumerateDisplayedIconViewsUsingBlock:")', bridge)
        self.assertIn("signature.numberOfArguments != 3", bridge)
        self.assertIn("methodReturnType", bridge)
        self.assertIn("getArgumentTypeAtIndex:2", bridge)

        self.assertIn("RFDisplayedIconViews(iconManager)", environment)
        self.assertIn("var candidates = systemDisplayedIconViews()", environment)
        self.assertIn(
            "candidates.append(contentsOf: windowScannedIconViews(matching: iconViewClass))",
            environment,
        )
        self.assertIn("foregroundWindows()", environment)
        self.assertIn('"SBIconLocationFloatingDock"', environment)
        self.assertIn('"SBIconLocationFloatingDockSuggestions"', environment)
        self.assertIn("let identifier = ObjectIdentifier(view)", environment)
        self.assertIn("if seen.insert(identifier).inserted", environment)
        self.assertIn("isEffectivelyVisible", environment)
        self.assertIn("isIconBusy", environment)

        production = header + bridge + environment
        self.assertNotIn("FloatingDockXVI", production)
        self.assertNotIn('NSClassFromString("UIImageView")', production)

    def test_custom_dock_scan_requires_explicit_icon_dock_semantics(self) -> None:
        environment = (ROOT / "Sources" / "SpringBoardEnvironment.swift").read_text(encoding="utf-8")

        self.assertIn("return hasExplicitDockSemantics(iconView)", environment)
        self.assertIn('readBool(iconView, selector: "isInDock") == true', environment)
        self.assertIn('RFInvokeObjectSelector(iconView, "location") as? String', environment)
        self.assertIn("dockIconLocations.contains(location)", environment)
        self.assertNotIn("return iconView.isKind(of: iconViewClass)", environment)

    def test_package_and_filter_are_ios15_springboard_only(self) -> None:
        control = (ROOT / "control").read_text(encoding="utf-8")
        self.assertRegex(control, r"(?m)^Package: com\.tsangbaby\.randomiconsflip$")
        self.assertRegex(control, r"(?m)^Depends: .*firmware \(>= 15\.0\).*$")

        with (ROOT / "RandomIconsFlip.plist").open("rb") as handle:
            filter_plist = plistlib.load(handle)
        self.assertEqual(filter_plist, {"Filter": {"Bundles": ["com.apple.springboard"]}})

    def test_roothide_build_contract(self) -> None:
        control = (ROOT / "control").read_text(encoding="utf-8")
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        workflow = (ROOT / ".github" / "workflows" / "build-roothide.yml").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertRegex(control, r"(?m)^Version: 0\.1\.0$")
        self.assertRegex(makefile, r"(?m)^PACKAGE_VERSION = 0\.1\.0$")
        self.assertRegex(control, r"(?m)^Maintainer: Tsangbaby$")
        self.assertRegex(control, r"(?m)^Author: Tsangbaby$")
        self.assertRegex(control, r"(?m)^Icon: https://tsangbaby\.github\.io/Icon/RandomIconFlip\.png$")
        self.assertRegex(
            control,
            r"(?m)^SileoDepiction: https://tsangbaby\.github\.io/depictions/com\.tsangbaby\.randomiconsflip/depiction\.json$",
        )
        self.assertRegex(control, r"(?m)^Conflicts: net\.limneos\.randomiconsflip$")
        self.assertRegex(control, r"(?m)^Replaces: net\.limneos\.randomiconsflip$")
        self.assertIn("runs-on: macos-14", workflow)
        self.assertIn("THEOS_PACKAGE_SCHEME: roothide", workflow)
        self.assertIn("SCHEME=roothide", workflow)
        self.assertIn("88506b2c22e9e07dd4ed055f23c9e398a117a2c7", workflow)
        self.assertIn("146e41ff2c292168388929e43c9b4de2f00e36b3", workflow)
        self.assertIn("iPhoneOS16.5.sdk", workflow)
        self.assertIn("TARGET=iphone:clang:16.5:15.0", workflow)
        self.assertIn("iphoneos-arm64e", workflow)
        self.assertIn("SOURCE_COMMIT.txt", workflow)
        self.assertIn("SHA256SUMS.txt", workflow)
        self.assertIn("actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683", workflow)
        self.assertIn("actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02", workflow)
        self.assertIn("com.tsangbaby.randomiconsflip", workflow)
        self.assertIn('PACKAGE_VERSION: "0.1.0"', workflow)
        self.assertIn('grep -Eq "^Version: ${PACKAGE_VERSION}$" control', workflow)
        self.assertIn('grep -Eq "^PACKAGE_VERSION = ${PACKAGE_VERSION}$" Makefile', workflow)
        self.assertIn("Run source contracts", workflow)
        self.assertIn("python3 -B -m unittest discover -s tests -p 'test_*.py' -v", workflow)
        self.assertIn("- 当前候选版本：RootHide `0.1.0`", readme)
        self.assertIn("Infinity Drift / Figure Eight（∞ 漂移 / 8 字巡航）", readme)
        self.assertIn("Rocket Launch（火箭升空）", readme)
        self.assertIn("Slingshot（弹弓弹射）", readme)
        self.assertIn("`0.0.8` 是当前实机验证基线", readme)
        self.assertIn("`0.1.0` 的 Rocket Launch / Slingshot 尚待实机验证", readme)
        self.assertIn("PACKAGE_VERSION=0.1.0", readme)
        self.assertNotIn("PACKAGE_VERSION: 0.0.7", workflow)
        self.assertNotIn("0\\.0\\.6", workflow)
        self.assertNotIn("rootless", workflow.lower())

    def test_active_identity_has_no_legacy_author_or_package(self) -> None:
        control = (ROOT / "control").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        notice = (ROOT / "NOTICE.md").read_text(encoding="utf-8")
        workflow = (ROOT / ".github" / "workflows" / "build-roothide.yml").read_text(encoding="utf-8")

        self.assertNotIn("Elias Limneos", control + readme)
        self.assertIn("Current author and maintainer: **tsangbaby**", notice)
        self.assertIn("Historical source attribution: **Elias Limneos**", notice)
        self.assertIn("tsangbaby", (readme + notice).lower())

        active_files = [
            ROOT / "Makefile",
            ROOT / "Tweak.xm",
            ROOT / "RuntimeBridge.m",
            ROOT / "RandomIconsFlip.plist",
            ROOT / "README.md",
            ROOT / "NOTICE.md",
        ]
        for path in active_files:
            self.assertNotIn("net.limneos.randomiconsflip", path.read_text(encoding="utf-8"))

        legacy_control_lines = [
            line for line in control.splitlines() if "net.limneos.randomiconsflip" in line
        ]
        self.assertEqual(
            legacy_control_lines,
            [
                "Conflicts: net.limneos.randomiconsflip",
                "Replaces: net.limneos.randomiconsflip",
            ],
        )

        legacy_workflow_lines = [
            line.strip() for line in workflow.splitlines() if "net.limneos.randomiconsflip" in line
        ]
        self.assertEqual(
            legacy_workflow_lines,
            [
                'test "$package_conflicts" = "net.limneos.randomiconsflip"',
                'test "$package_replaces" = "net.limneos.randomiconsflip"',
            ],
        )

    def test_public_source_contains_no_embedded_secrets(self) -> None:
        text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in ROOT.rglob("*")
            if path.is_file()
            and ".git" not in path.parts
            and path.suffix.lower() in {".swift", ".xm", ".h", ".md", ".plist", ".yml", ".yaml", ""}
        )
        self.assertIsNone(re.search(r"sk-[A-Za-z0-9_-]{20,}", text))
        self.assertNotIn("BEGIN PRIVATE KEY", text)


if __name__ == "__main__":
    unittest.main()
