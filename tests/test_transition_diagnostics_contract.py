from __future__ import annotations

import re
import hashlib
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTICS_VERSION = "0.0.9~diag4"


class AppToHomeDiagnosticsContract(unittest.TestCase):
    def source(self) -> str:
        path = ROOT / "TransitionDiagnostics.m"
        self.assertTrue(path.is_file(), "TransitionDiagnostics.m must be a standalone module")
        return path.read_text(encoding="utf-8")

    def test_diagnostic_build_is_explicit_and_separate_from_release(self) -> None:
        control = (ROOT / "control").read_text(encoding="utf-8")
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        workflow = (ROOT / ".github" / "workflows" / "build-roothide.yml").read_text(
            encoding="utf-8"
        )
        guide_path = ROOT / "DIAGNOSTICS.md"

        self.assertRegex(control, rf"(?m)^Version: {re.escape(DIAGNOSTICS_VERSION)}$")
        self.assertRegex(makefile, rf"(?m)^PACKAGE_VERSION = {re.escape(DIAGNOSTICS_VERSION)}$")
        self.assertIn(f'PACKAGE_VERSION: "{DIAGNOSTICS_VERSION}"', workflow)
        self.assertIn("Diagnostic", control)
        self.assertTrue(guide_path.is_file())
        guide = guide_path.read_text(encoding="utf-8")
        self.assertIn("0.0.8", guide)
        self.assertIn(DIAGNOSTICS_VERSION, guide)
        self.assertIn("iOS 15.4.1", guide)
        self.assertIn("iOS 16.0.3", guide)
        self.assertIn(
            "/var/mobile/Library/RandomIconsFlipDiagnostics/com.tsangbaby.randomiconsflip.transitiondiag.plist",
            guide,
        )
        self.assertIn("/tmp/com.tsangbaby.randomiconsflip.transitiondiag.status.txt", guide)

    def test_diag4_uses_private_mobile_sink_and_fixed_low_level_status_file(self) -> None:
        source = self.source()

        self.assertIn(
            'return @"/var/mobile/Library/RandomIconsFlipDiagnostics/com.tsangbaby.randomiconsflip.transitiondiag.plist";',
            source,
        )
        self.assertNotIn(
            'return @"/var/mobile/Library/Preferences/com.tsangbaby.randomiconsflip.transitiondiag.plist";',
            source,
        )
        self.assertNotIn("NSSearchPathForDirectoriesInDomains", source)
        self.assertIn(
            '"/tmp/com.tsangbaby.randomiconsflip.transitiondiag.status.txt"', source
        )
        for required in (
            "RFDiagnosticStage",
            "RFWriteDiagnosticStatus",
            "RFDiagnosticWriteResult",
            "RFDiagnosticStageForWriteResult",
            '"entry"',
            '"queue-ready"',
            '"inventory-ready"',
            '"hooks-ready"',
            '"plist-write-ok"',
            '"plist-protection-failed"',
            "O_NOFOLLOW",
            "O_NONBLOCK",
            "fstat",
            "S_ISREG",
            "st_uid != geteuid()",
            "st_nlink != 1",
            "fchmod",
            "ftruncate",
        ):
            self.assertIn(required, source)

        self.assertNotIn("exception.reason", source)
        self.assertNotIn("exception.name", source)

    def test_diag4_status_writes_are_async_and_lifetime_bounded(self) -> None:
        source = self.source()

        self.assertIn("static dispatch_queue_t RFDiagnosticStatusQueue", source)
        self.assertIn("RFEnqueueDiagnosticStatus", source)
        self.assertIn("dispatch_async(RFDiagnosticStatusQueue", source)
        self.assertNotIn("dispatch_sync(RFDiagnosticStatusQueue", source)
        self.assertEqual(source.count("RFWriteDiagnosticStatus("), 2)
        self.assertIn("RFMaximumStoredEvents = 128", source)

    def test_probe_is_started_separately_and_hooks_only_after_abi_validation(self) -> None:
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        tweak = (ROOT / "Tweak.xm").read_text(encoding="utf-8")
        header_path = ROOT / "TransitionDiagnostics.h"
        source = self.source()

        self.assertTrue(header_path.is_file())
        header = header_path.read_text(encoding="utf-8")
        self.assertIn("#ifdef __cplusplus", header)
        self.assertIn('extern "C" {', header)
        self.assertIn("TransitionDiagnostics.m", makefile)
        self.assertIn('#import "TransitionDiagnostics.h"', tweak)
        self.assertIn("RFTransitionDiagnosticsStart();", tweak)
        self.assertIn("method_getTypeEncoding", source)
        self.assertIn("NSMethodSignature", source)
        self.assertIn("MSHookMessageEx", source)
        self.assertIn("RFInstallZeroArgumentLifecycleHook", source)
        self.assertIn("unsupportedSignature", source)
        self.assertIn("originalIMP", source)

        manager_start = tweak.index("[[RandomFlipManager sharedManager] start];")
        diagnostic_start = tweak.index("RFTransitionDiagnosticsStart();")
        self.assertLess(manager_start, diagnostic_start)
        self.assertIn("@try", tweak)
        self.assertIn("@catch", tweak)

    def test_each_hook_has_a_static_trampoline_and_direct_predecessor_publication(self) -> None:
        source = self.source()

        self.assertIn("RF_DEFINE_VOID_LIFECYCLE_HOOK", source)
        self.assertIn("MSHookMessageEx(targetClass, selector, replacementIMP, originalSlot)", source)
        self.assertIn("RFSafelyRecordLifecycleEvent", source)
        self.assertNotIn("RFHookInstallLock", source)
        self.assertNotIn("substrateOriginalIMP", source)
        self.assertNotIn("RFHookReturnKindObject", source)
        self.assertNotIn("imp_implementationWithBlock", source)
        self.assertNotIn("class_getMethodImplementation", source)
        self.assertNotIn("method_getImplementation", source)
        self.assertNotIn("RFOriginalIMPs", source)
        self.assertNotIn("RFHookEvents", source)
        self.assertNotIn("RFLookupOriginalValue", source)
        self.assertNotIn("RFLookupEventName", source)
        self.assertNotIn("RFOriginalImplementation", source)

    def test_transaction_begin_bool_hook_returns_original_exactly_once(self) -> None:
        source = self.source()

        self.assertIn("RFHookReturnKindBool", source)
        self.assertIn("RF_DEFINE_BOOL_LIFECYCLE_HOOK", source)
        self.assertIn("RFSafelyRecordLifecycleBooleanEvent", source)
        self.assertIn(
            '{ "SBToAppsWorkspaceTransaction", "_beginAnimation", '
            '(IMP)RFTransactionBeginHookReplacement, '
            '&RFTransactionBeginHookOriginalIMP, RFHookReturnKindBool }',
            source,
        )

        macro_start = source.index("#define RF_DEFINE_BOOL_LIFECYCLE_HOOK")
        macro_end = source.index("\nRF_DEFINE_BOOL_LIFECYCLE_HOOK(", macro_start)
        macro = source[macro_start:macro_end]
        original_call = "((BOOL (*)(id, SEL))originalIMP)(object, selector)"
        self.assertEqual(macro.count(original_call), 1)
        self.assertLess(macro.index(original_call), macro.index("RFSafelyRecordLifecycleBooleanEvent"))
        self.assertLess(macro.index("RFSafelyRecordLifecycleBooleanEvent"), macro.index("return result"))
        self.assertNotIn(
            "RF_DEFINE_VOID_LIFECYCLE_HOOK(RFTransactionBeginHook", source
        )

    def test_geometry_hooks_are_exact_abi_gated_and_per_hook_bounded(self) -> None:
        source = self.source()

        for required in (
            "RFMaximumGeometryEventsPerHook = 8",
            "RFReserveGeometryEventSlot",
            "RFShouldCaptureGeometryEvent",
            "RFGeometryReturnKindCGRectIndex",
            "RFGeometryReturnKindDoubleIndex",
            "RFGeometryReturnKindCornerRadiiIndex",
            "RFGeometryReturnKindObjectPoint",
            "RFInstallGeometryHook",
            "RF_DEFINE_CGRECT_INDEX_GEOMETRY_HOOK",
            "RF_DEFINE_DOUBLE_INDEX_GEOMETRY_HOOK",
            "RF_DEFINE_CORNER_RADII_INDEX_GEOMETRY_HOOK",
            "RF_DEFINE_OBJECT_POINT_GEOMETRY_HOOK",
            "RFEnqueueGeometryEvent",
            "geometryHooks",
            "if (!NSThread.isMainThread)",
            '"geometryIndex"',
            '"frameX"',
            '"frameWidth"',
            '"scale"',
            '"cornerTopLeft"',
            '"targetCenterX"',
            '"resultPresent"',
        ):
            self.assertIn(required, source)

        for specification in (
            '{ "SBFullScreenToHomeIconZoomSwitcherModifier", "frameForIndex:", '
            '(IMP)RFIconFrameGeometryHookReplacement, &RFIconFrameGeometryHookOriginalIMP, '
            'RFGeometryHookIDIconFrame, RFGeometryReturnKindCGRectIndex, '
            '"{CGRect={CGPoint=dd}{CGSize=dd}}24@0:8Q16" }',
            '{ "SBFullScreenToHomeIconZoomSwitcherModifier", "scaleForIndex:", '
            '(IMP)RFIconScaleGeometryHookReplacement, &RFIconScaleGeometryHookOriginalIMP, '
            'RFGeometryHookIDIconScale, RFGeometryReturnKindDoubleIndex, "d24@0:8Q16" }',
            '{ "SBFullScreenToHomeIconZoomSwitcherModifier", "cornerRadiiForIndex:", '
            '(IMP)RFIconCornerGeometryHookReplacement, &RFIconCornerGeometryHookOriginalIMP, '
            'RFGeometryHookIDIconCornerRadii, RFGeometryReturnKindCornerRadiiIndex, '
            '"{UIRectCornerRadii=dddd}24@0:8Q16" }',
            '{ "SBFullScreenToHomeIconZoomSwitcherModifier", "layoutSettingsForTargetCenter:", '
            '(IMP)RFIconLayoutGeometryHookReplacement, &RFIconLayoutGeometryHookOriginalIMP, '
            'RFGeometryHookIDIconLayout, RFGeometryReturnKindObjectPoint, '
            '"@32@0:8{CGPoint=dd}16" }',
            '{ "SBFullScreenToHomeCenterZoomDownSwitcherModifier", "frameForIndex:", '
            '(IMP)RFCenterFrameGeometryHookReplacement, &RFCenterFrameGeometryHookOriginalIMP, '
            'RFGeometryHookIDCenterFrame, RFGeometryReturnKindCGRectIndex, '
            '"{CGRect={CGPoint=dd}{CGSize=dd}}24@0:8Q16" }',
            '{ "SBFullScreenToHomeSystemApertureSwitcherModifier", "frameForIndex:", '
            '(IMP)RFSystemApertureFrameGeometryHookReplacement, &RFSystemApertureFrameGeometryHookOriginalIMP, '
            'RFGeometryHookIDSystemApertureFrame, RFGeometryReturnKindCGRectIndex, '
            '"{CGRect={CGPoint=dd}{CGSize=dd}}24@0:8Q16" }',
        ):
            self.assertIn(specification, source)

        macro_fields = {
            "RF_DEFINE_CGRECT_INDEX_GEOMETRY_HOOK": "RFGeometryFieldsForCGRect",
            "RF_DEFINE_DOUBLE_INDEX_GEOMETRY_HOOK": "RFGeometryFieldsForDouble",
            "RF_DEFINE_CORNER_RADII_INDEX_GEOMETRY_HOOK": "RFGeometryFieldsForCornerRadii",
            "RF_DEFINE_OBJECT_POINT_GEOMETRY_HOOK": "RFGeometryFieldsForObjectPoint",
        }
        for macro_name, fields_builder in macro_fields.items():
            start = source.index(f"#define {macro_name}")
            next_define = source.find("\n#define ", start + 1)
            macro = source[start:] if next_define < 0 else source[start:next_define]
            self.assertEqual(macro.count("originalIMP)(object, selector"), 1, macro_name)
            self.assertEqual(macro.count("if (RFShouldCaptureGeometryEvent(HOOK_ID))"), 1, macro_name)
            self.assertEqual(macro.count(fields_builder), 1, macro_name)
            self.assertLess(
                macro.index("originalIMP)(object, selector"),
                macro.index("if (RFShouldCaptureGeometryEvent(HOOK_ID))"),
            )
            self.assertLess(
                macro.index("if (RFShouldCaptureGeometryEvent(HOOK_ID))"),
                macro.index("RFSafelyRecordGeometryEvent"),
            )
            self.assertLess(macro.index("RFSafelyRecordGeometryEvent"), macro.index(fields_builder))
            self.assertLess(macro.index(fields_builder), macro.index("return result"))

        self.assertIn(
            "typedef struct {\n"
            "\tCGFloat topLeft;\n"
            "\tCGFloat bottomLeft;\n"
            "\tCGFloat bottomRight;\n"
            "\tCGFloat topRight;\n"
            "} RFDiagnosticCornerRadii;",
            source,
        )
        self.assertIn("strcmp(rawEncoding, expectedEncoding) != 0", source)
        self.assertNotIn("RFGeometryAdmissionLock", source)
        reserve_start = source.index("static BOOL RFReserveGeometryEventSlot")
        reserve_end = source.index("static UIWindowScene *RFMainWindowScene", reserve_start)
        reserve = source[reserve_start:reserve_end]
        self.assertLess(
            reserve.index("RFGeometryEventsAdmitted[hookID] >= RFMaximumGeometryEventsPerHook"),
            reserve.index("RFReserveEventSlot()"),
        )
        gate_start = source.index("static BOOL RFShouldCaptureGeometryEvent")
        gate_end = source.index("static void RFEnqueueGeometryEvent", gate_start)
        gate = source[gate_start:gate_end]
        self.assertLess(gate.index("if (!NSThread.isMainThread)"), gate.index("RFReserveGeometryEventSlot"))
        self.assertNotIn("class_getMethodImplementation", source)
        self.assertNotIn("method_getImplementation", source)

    def test_inventory_and_lifecycle_scope_cover_both_target_systems(self) -> None:
        source = self.source()

        for class_name in (
            "SBToAppsWorkspaceTransaction",
            "SBWorkspaceApplicationSceneTransitionContext",
            "SBFullScreenToHomeIconZoomSwitcherModifier",
            "SBFullScreenToHomeCenterZoomDownSwitcherModifier",
            "SBHomeGestureToHomeSwitcherModifier",
            "SBHomeGestureFinalDestinationSwitcherModifier",
            "SBFullScreenToHomeSystemApertureSwitcherModifier",
            "SBFluidSwitcherAnimationController",
        ):
            self.assertIn(class_name, source)

        for selector_name in (
            "isGoingToLauncher",
            "_transitionWasCancelled",
            "_transitionContext",
            "interfaceOrientation",
            "interfaceOrientationOrPreferredOrientation",
            "_beginAnimation",
            "_animationDidFinish",
            "transitionWillBegin",
            "transitionDidEnd",
            "frameForIndex:",
            "scaleForIndex:",
            "cornerRadiiForIndex:",
        ):
            self.assertIn(selector_name, source)

        self.assertIn("transaction.begin", source)
        self.assertIn("transaction.finish", source)
        self.assertIn("modifier.begin", source)
        self.assertIn("modifier.end", source)

    def test_output_is_bounded_private_and_contains_only_geometry_capabilities(self) -> None:
        source = self.source()

        for required in (
            "[RFAppToHomeDiag]",
            "com.tsangbaby.randomiconsflip.transitiondiag.plist",
            "RFMaximumStoredEvents = 128",
            "RFReserveEventSlot",
            "RFEventsAdmitted >= RFMaximumStoredEvents",
            "F_SETPROTECTIONCLASS",
            "F_GETPROTECTIONCLASS",
            "RFProtectionClassC",
            "osVersion",
            "osBuild",
            "screenWidth",
            "screenHeight",
            "screenScale",
            "safeAreaTop",
            "safeAreaBottom",
            "sceneInterfaceOrientation",
            "contextInterfaceOrientation",
            "portrait",
            "reduceMotion",
        ):
            self.assertIn(required, source)

        forbidden = (
            "bundleIdentifier",
            "displayIdentifier",
            "processIdentifier",
            "snapshotViewAfterScreenUpdates",
            "drawViewHierarchyInRect",
            "UIGraphicsImageRenderer",
            "UIImagePNGRepresentation",
            "touchesBegan",
            "touchesMoved",
            "locationInView",
            "UIWindow alloc",
            "removeAllAnimations",
        )
        for token in forbidden:
            self.assertNotIn(token, source)

        self.assertNotIn("dispatch_async(dispatch_get_main_queue()", source)

    def test_writer_is_exception_contained_and_sink_is_private_before_data_write(self) -> None:
        source = self.source()

        for required in (
            "#import <fcntl.h>",
            "#import <string.h>",
            "#import <stdlib.h>",
            "#import <sys/stat.h>",
            "#import <unistd.h>",
            "O_NOFOLLOW",
            "O_CLOEXEC",
            "O_NONBLOCK",
            "O_DIRECTORY",
            "openat",
            "fstatat",
            "AT_SYMLINK_NOFOLLOW",
            "fstat",
            "S_ISREG",
            "st_uid != geteuid()",
            "st_nlink != 1",
            "st_dev",
            "st_ino",
            "S_IWGRP",
            "S_IWOTH",
            "outputCreated",
            "openedStatusValid",
            "outputValidated",
            "fchmod",
            "unlinkat",
            "@autoreleasepool",
            "writerException",
        ):
            self.assertIn(required, source)

        secure_open = source.index("O_NOFOLLOW")
        data_write = source.index("RFWriteAllBytes(fileDescriptor")
        self.assertLess(secure_open, data_write)
        self.assertEqual(source.count("O_NONBLOCK"), 5)
        self.assertNotIn("renameat", source)
        self.assertNotIn("temporaryFileName", source)

    def test_exception_output_uses_only_fixed_markers(self) -> None:
        source = self.source()
        tweak = (ROOT / "Tweak.xm").read_text(encoding="utf-8")

        for fixed_marker in (
            "installationException",
            "writerException",
            "startupException",
            "startupBoundaryException",
        ):
            self.assertIn(fixed_marker, source + tweak)
        for forbidden in (
            "exception.name",
            "exception.reason",
            '[@"exception"]',
            '@"exception":',
        ):
            self.assertNotIn(forbidden, source + tweak)

    def test_ci_runs_contracts_and_verifies_scope_markers_and_signature_structure(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "build-roothide.yml").read_text(
            encoding="utf-8"
        )
        verifier = ROOT / "tests" / "verify_macho_signature.py"

        self.assertIn("Run source contracts", workflow)
        self.assertIn("PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover", workflow)
        self.assertIn("plistlib", workflow)
        self.assertIn("com.apple.springboard", workflow)
        self.assertIn("[RFAppToHomeDiag]", workflow)
        self.assertIn(DIAGNOSTICS_VERSION, workflow)
        self.assertIn("grep -Fq 'frameForIndex:'", workflow)
        self.assertIn("grep -Fq 'scaleForIndex:'", workflow)
        self.assertIn("grep -Fq 'cornerRadiiForIndex:'", workflow)
        self.assertIn("grep -Fq 'layoutSettingsForTargetCenter:'", workflow)
        self.assertIn("grep -Fq 'geometryHooks'", workflow)
        self.assertIn("verify_macho_signature.py", workflow)
        self.assertIn("@loader_path/.jbroot/usr/lib/libsubstrate.dylib", workflow)
        self.assertIn("otool -L", workflow)
        self.assertIn('ldid -e "$candidate"', workflow)
        self.assertIn('python3 tests/verify_macho_signature.py "$candidate"', workflow)
        self.assertNotIn("codesign --verify", workflow)
        self.assertTrue(verifier.is_file())

    def test_signature_verifier_accepts_only_bounded_superblob_with_code_directory(self) -> None:
        verifier = ROOT / "tests" / "verify_macho_signature.py"
        self.assertTrue(verifier.is_file())

        identifier = b"com.tsangbaby.signature-test\0"
        code_directory_length = 44 + len(identifier) + 32
        superblob_length = 20 + code_directory_length
        load_command = struct.pack("<IIII", 0x1D, 16, 48, superblob_length)
        header = struct.pack("<IiiIIIII", 0xFEEDFACF, 0x0100000C, 2, 6, 1, 16, 0, 0)
        signed_prefix = header + load_command
        code_hash = hashlib.sha256(signed_prefix).digest()
        code_directory = (
            struct.pack(
                ">9I4BI",
                0xFADE0C02,
                code_directory_length,
                0x20001,
                0,
                44 + len(identifier),
                44,
                0,
                1,
                len(signed_prefix),
                32,
                2,
                0,
                12,
                0,
            )
            + identifier
            + code_hash
        )
        superblob = (
            struct.pack(">III", 0xFADE0CC0, 20 + len(code_directory), 1)
            + struct.pack(">II", 0, 20)
            + code_directory
        )

        empty_code_directory = struct.pack(">II", 0xFADE0C02, 8)
        empty_superblob = (
            struct.pack(">III", 0xFADE0CC0, 20 + len(empty_code_directory), 1)
            + struct.pack(">II", 0, 20)
            + empty_code_directory
        )
        empty_load_command = struct.pack("<IIII", 0x1D, 16, 48, len(empty_superblob))

        with tempfile.TemporaryDirectory() as directory:
            valid = Path(directory) / "valid.macho"
            truncated = Path(directory) / "truncated.macho"
            empty = Path(directory) / "empty-code-directory.macho"
            bad_hash = Path(directory) / "bad-hash.macho"
            trailing = Path(directory) / "unsigned-trailing-data.macho"
            valid_bytes = signed_prefix + superblob
            valid.write_bytes(valid_bytes)
            truncated.write_bytes(valid_bytes[:-1])
            empty.write_bytes(header + empty_load_command + empty_superblob)
            mutated = bytearray(valid_bytes)
            mutated[-1] ^= 0xFF
            bad_hash.write_bytes(mutated)
            trailing.write_bytes(valid_bytes + b"unsigned trailing data")

            accepted = subprocess.run(
                ["python3", str(verifier), str(valid)], capture_output=True, text=True
            )
            self.assertEqual(accepted.returncode, 0, accepted.stderr)
            for invalid in (truncated, empty, bad_hash, trailing):
                rejected = subprocess.run(
                    ["python3", str(verifier), str(invalid)], capture_output=True, text=True
                )
                self.assertNotEqual(rejected.returncode, 0, invalid.name)

    def test_signature_verifier_rejects_partial_code_coverage(self) -> None:
        verifier = ROOT / "tests" / "verify_macho_signature.py"
        identifier = b"com.tsangbaby.partial-coverage\0"
        header = struct.pack("<IiiIIIII", 0xFEEDFACF, 0x0100000C, 2, 6, 1, 16, 0, 0)
        code_directory_length = 44 + len(identifier) + 32
        superblob_length = 20 + code_directory_length
        load_command = struct.pack("<IIII", 0x1D, 16, 48, superblob_length)
        signed_prefix = header + load_command
        partial_code_limit = 32
        code_directory = (
            struct.pack(
                ">9I4BI",
                0xFADE0C02,
                code_directory_length,
                0x20001,
                0,
                44 + len(identifier),
                44,
                0,
                1,
                partial_code_limit,
                32,
                2,
                0,
                12,
                0,
            )
            + identifier
            + hashlib.sha256(signed_prefix[:partial_code_limit]).digest()
        )
        superblob = (
            struct.pack(">III", 0xFADE0CC0, superblob_length, 1)
            + struct.pack(">II", 0, 20)
            + code_directory
        )

        with tempfile.TemporaryDirectory() as directory:
            partial = Path(directory) / "partial-coverage.macho"
            partial.write_bytes(signed_prefix + superblob)
            rejected = subprocess.run(
                ["python3", str(verifier), str(partial)], capture_output=True, text=True
            )
            self.assertNotEqual(rejected.returncode, 0, rejected.stdout)

    def test_signature_verifier_rejects_unsupported_versions_and_conflicting_limits(self) -> None:
        verifier = ROOT / "tests" / "verify_macho_signature.py"
        header = struct.pack("<IiiIIIII", 0xFEEDFACF, 0x0100000C, 2, 6, 1, 16, 0, 0)

        def build_code_directory(version: int, base_size: int, code_limit_32: int, code_limit_64: int) -> bytes:
            identifier = b"com.tsangbaby.version-limit-test\0"
            code_directory_length = base_size + len(identifier) + 32
            superblob_length = 20 + code_directory_length
            load_command = struct.pack("<IIII", 0x1D, 16, 48, superblob_length)
            signed_prefix = header + load_command
            extension = bytearray(base_size - 44)
            if base_size >= 64:
                struct.pack_into(">Q", extension, 12, code_limit_64)
            code_directory = (
                struct.pack(
                    ">9I4BI",
                    0xFADE0C02,
                    code_directory_length,
                    version,
                    0,
                    base_size + len(identifier),
                    base_size,
                    0,
                    1,
                    code_limit_32,
                    32,
                    2,
                    0,
                    12,
                    0,
                )
                + bytes(extension)
                + identifier
                + hashlib.sha256(signed_prefix).digest()
            )
            superblob = (
                struct.pack(">III", 0xFADE0CC0, superblob_length, 1)
                + struct.pack(">II", 0, 20)
                + code_directory
            )
            return signed_prefix + superblob

        malformed = {
            "too-old.macho": build_code_directory(0x20000, 44, 48, 0),
            "too-new.macho": build_code_directory(0x20601, 108, 48, 0),
            "conflicting-limits.macho": build_code_directory(0x20300, 64, 48, 48),
        }
        with tempfile.TemporaryDirectory() as directory:
            for name, contents in malformed.items():
                with self.subTest(name=name):
                    path = Path(directory) / name
                    path.write_bytes(contents)
                    rejected = subprocess.run(
                        ["python3", str(verifier), str(path)], capture_output=True, text=True
                    )
                    self.assertNotEqual(rejected.returncode, 0, f"{name}: {rejected.stdout}")

    def test_signature_verifier_enforces_code_directory_slots(self) -> None:
        verifier = ROOT / "tests" / "verify_macho_signature.py"
        header = struct.pack("<IiiIIIII", 0xFEEDFACF, 0x0100000C, 2, 6, 1, 16, 0, 0)
        identifier = b"com.tsangbaby.slot-test\0"
        code_directory_length = 44 + len(identifier) + 32

        def build_slots(slot_types: list[int]) -> bytes:
            index_end = 12 + 8 * len(slot_types)
            superblob_length = index_end + code_directory_length * len(slot_types)
            load_command = struct.pack("<IIII", 0x1D, 16, 48, superblob_length)
            signed_prefix = header + load_command
            code_directory = (
                struct.pack(
                    ">9I4BI",
                    0xFADE0C02,
                    code_directory_length,
                    0x20001,
                    0,
                    44 + len(identifier),
                    44,
                    0,
                    1,
                    len(signed_prefix),
                    32,
                    2,
                    0,
                    12,
                    0,
                )
                + identifier
                + hashlib.sha256(signed_prefix).digest()
            )
            indices = b"".join(
                struct.pack(">II", slot_type, index_end + index * code_directory_length)
                for index, slot_type in enumerate(slot_types)
            )
            return (
                signed_prefix
                + struct.pack(">III", 0xFADE0CC0, superblob_length, len(slot_types))
                + indices
                + code_directory * len(slot_types)
            )

        malformed = {
            "illegal-slot.macho": build_slots([0xDEADBEEF]),
            "alternate-without-primary.macho": build_slots([0x1000]),
            "duplicate-primary-slot.macho": build_slots([0, 0]),
        }
        with tempfile.TemporaryDirectory() as directory:
            valid = Path(directory) / "primary-and-alternate.macho"
            valid.write_bytes(build_slots([0, 0x1000]))
            accepted = subprocess.run(
                ["python3", str(verifier), str(valid)], capture_output=True, text=True
            )
            self.assertEqual(accepted.returncode, 0, accepted.stderr)

            for name, contents in malformed.items():
                with self.subTest(name=name):
                    path = Path(directory) / name
                    path.write_bytes(contents)
                    rejected = subprocess.run(
                        ["python3", str(verifier), str(path)], capture_output=True, text=True
                    )
                    self.assertNotEqual(rejected.returncode, 0, f"{name}: {rejected.stdout}")

    def test_capture_budget_bounds_pending_and_lifetime_work(self) -> None:
        source = self.source()

        self.assertIn("static NSUInteger RFEventsAdmitted = 0", source)
        self.assertIn("os_unfair_lock_lock(&RFAdmissionLock)", source)
        self.assertIn("os_unfair_lock_unlock(&RFAdmissionLock)", source)
        self.assertEqual(source.count("dispatch_async(RFDiagnosticWriterQueue"), 2)
        self.assertNotIn("event=%@ class=%@ selector=%@ sequence=%lu", source)

    def test_no_animation_or_window_mutation_is_introduced(self) -> None:
        source = self.source()

        for forbidden in (
            "UIView animate",
            "UIViewPropertyAnimator",
            "CGAffineTransform",
            ".transform =",
            ".frame =",
            ".center =",
            ".alpha =",
            "setFrame:",
            "setTransform:",
            "setAlpha:",
            "addSubview:",
            "removeFromSuperview",
        ):
            self.assertNotIn(forbidden, source)

    def test_integer_selector_bridge_is_strictly_type_checked(self) -> None:
        header = (ROOT / "RandomIconsFlip-Bridging-Header.h").read_text(encoding="utf-8")
        bridge = (ROOT / "RuntimeBridge.m").read_text(encoding="utf-8")

        self.assertIn("RFReadIntegerSelector", header)
        self.assertIn("RFReadIntegerSelector", bridge)
        self.assertIn("returnType[0] != 'q' && returnType[0] != 'Q'", bridge)
        self.assertIn("methodSignatureForSelector", bridge)

    def test_reduce_motion_uses_objective_c_uikit_api(self) -> None:
        source = self.source()
        self.assertIn("UIAccessibilityIsReduceMotionEnabled()", source)
        self.assertNotIn("UIAccessibility.isReduceMotionEnabled", source)

    def test_unknown_context_orientation_falls_back_to_scene_orientation(self) -> None:
        source = self.source()

        for required in (
            '@"schemaVersion": @2',
            "contextOrientationKnown",
            "contextOrientationValue != UIInterfaceOrientationUnknown",
            "effectiveInterfaceOrientation",
            "effectiveOrientationSource",
            '@"scene"',
            '@"context"',
        ):
            self.assertIn(required, source)

        self.assertNotIn(
            "NSInteger effectiveOrientation = contextOrientation != nil", source
        )


if __name__ == "__main__":
    unittest.main()
