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

    def test_random_animation_pool_uses_seven_transform_safe_styles(self) -> None:
        manager = (ROOT / "Sources" / "RandomFlipManager.swift").read_text(encoding="utf-8")

        for style in (
            "flip",
            "bounce",
            "wiggle",
            "rotation",
            "horizontalShake",
            "jumpLanding",
            "jelly",
        ):
            self.assertIn(f"case {style}", manager)

        pool = re.search(
            r"private static let animationPool: \[IconAnimationStyle\] = \[(.*?)\]",
            manager,
            re.DOTALL,
        )
        self.assertIsNotNone(pool)
        styles = re.findall(
            r"\.(flip|bounce|wiggle|rotation|horizontalShake|jumpLanding|jelly)",
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
        ):
            self.assertIn(f"private func {helper}", manager)
        self.assertIn("UIView.animateKeyframes", manager)
        self.assertGreaterEqual(manager.count("let baseTransform = view.transform"), 6)
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

        self.assertRegex(control, r"(?m)^Version: 0\.0\.5$")
        self.assertRegex(makefile, r"(?m)^PACKAGE_VERSION = 0\.0\.5$")
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
        self.assertIn("PACKAGE_VERSION: 0.0.5", workflow)
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
