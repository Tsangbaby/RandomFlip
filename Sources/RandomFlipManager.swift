import Foundation
import UIKit

@MainActor
@objc(RandomFlipManager)
public final class RandomFlipManager: NSObject {
    private enum IconAnimationStyle {
        case flip
        case bounce
        case wiggle
        case rotation
        case horizontalShake
        case jumpLanding
        case jelly
        case orbitSpiral
        case flutterLeaf
        case infinityDrift
        case rocketLaunch
        case slingshot
    }

    private static let singleton = RandomFlipManager(environment: SpringBoardEnvironment())

    private static let initialDelay: TimeInterval = 1.5
    private static let requiredConsecutiveReadyTicks = 2
    private static let animationPool: [IconAnimationStyle] = [
        .flip,
        .bounce, .bounce,
        .wiggle, .wiggle,
        .rotation, .rotation,
        .horizontalShake, .horizontalShake,
        .jumpLanding, .jumpLanding,
        .jelly, .jelly,
        .orbitSpiral, .orbitSpiral,
        .flutterLeaf, .flutterLeaf,
        .infinityDrift, .infinityDrift,
        .rocketLaunch, .rocketLaunch,
        .slingshot, .slingshot
    ]

    private let environment: SpringBoardEnvironment
    private var pendingTick: DispatchWorkItem?
    private var isRunning = false
    private var isAnimating = false
    private var consecutiveReadyTicks = 0
    private var scheduleGeneration: UInt64 = 0
    private var animationSequence: UInt64 = 0
    private weak var activeAnimationView: UIView?

    private init(environment: SpringBoardEnvironment) {
        self.environment = environment
        super.init()
    }

    @objc(sharedManager)
    public class func sharedManager() -> RandomFlipManager {
        return singleton
    }

    @objc(start)
    public func start() {
        guard Thread.isMainThread else {
            DispatchQueue.main.async { [weak self] in
                self?.start()
            }
            return
        }

        guard !isRunning else {
            return
        }

        isRunning = true
        consecutiveReadyTicks = 0
        scheduleGeneration &+= 1
        scheduleNext(after: Self.initialDelay)
    }

    @objc(stop)
    public func stop() {
        guard Thread.isMainThread else {
            DispatchQueue.main.async { [weak self] in
                self?.stop()
            }
            return
        }

        guard isRunning || pendingTick != nil else {
            return
        }

        isRunning = false
        consecutiveReadyTicks = 0
        scheduleGeneration &+= 1
        pendingTick?.cancel()
        pendingTick = nil
    }

    private func scheduleNext(after explicitDelay: TimeInterval? = nil) {
        precondition(Thread.isMainThread)
        guard isRunning else {
            return
        }

        pendingTick?.cancel()

        let expectedGeneration = scheduleGeneration
        let workItem = DispatchWorkItem { [weak self] in
            guard let self = self,
                  self.isRunning,
                  self.scheduleGeneration == expectedGeneration else {
                return
            }

            self.pendingTick = nil
            self.performTick()
        }

        pendingTick = workItem
        let delay = explicitDelay ?? Self.nextAttemptDelay()
        let milliseconds = max(1, Int((delay * 1_000).rounded()))
        DispatchQueue.main.asyncAfter(
            deadline: .now() + .milliseconds(milliseconds),
            execute: workItem
        )
    }

    private func performTick() {
        precondition(Thread.isMainThread)
        guard isRunning else {
            return
        }

        defer {
            scheduleNext()
        }

        guard !isAnimating else {
            return
        }

        guard !UIAccessibility.isReduceMotionEnabled,
              let animationView = environment.randomAnimationTarget() else {
            consecutiveReadyTicks = 0
            return
        }

        consecutiveReadyTicks = min(
            consecutiveReadyTicks + 1,
            Self.requiredConsecutiveReadyTicks
        )
        guard consecutiveReadyTicks >= Self.requiredConsecutiveReadyTicks else {
            return
        }

        beginAnimation(on: animationView)
    }

    private func beginAnimation(on view: UIView) {
        precondition(Thread.isMainThread)

        isAnimating = true
        activeAnimationView = view
        animationSequence &+= 1

        let token = animationSequence
        let duration = Self.nextAnimationDuration()
        let style = Self.animationPool.randomElement() ?? .flip
        let completion: (Bool) -> Void = { [weak self, weak view] _ in
            self?.finishAnimation(token: token, expectedView: view)
        }

        switch style {
        case .flip:
            animateFlip(on: view, duration: duration, completion: completion)
        case .bounce:
            animateBounce(on: view, duration: duration, completion: completion)
        case .wiggle:
            animateWiggle(on: view, duration: duration, completion: completion)
        case .rotation:
            animateRotation(on: view, duration: duration, completion: completion)
        case .horizontalShake:
            animateHorizontalShake(on: view, duration: duration, completion: completion)
        case .jumpLanding:
            animateJumpLanding(on: view, duration: duration, completion: completion)
        case .jelly:
            animateJelly(on: view, duration: duration, completion: completion)
        case .orbitSpiral:
            animateOrbitSpiral(on: view, duration: duration, completion: completion)
        case .flutterLeaf:
            animateFlutterLeaf(on: view, duration: duration, completion: completion)
        case .infinityDrift:
            animateInfinityDrift(on: view, duration: duration, completion: completion)
        case .rocketLaunch:
            animateRocketLaunch(on: view, duration: duration, completion: completion)
        case .slingshot:
            animateSlingshot(on: view, duration: duration, completion: completion)
        }
    }

    private func animateFlip(
        on view: UIView,
        duration: TimeInterval,
        completion: @escaping (Bool) -> Void
    ) {
        let direction: UIView.AnimationOptions = Bool.random()
            ? .transitionFlipFromLeft
            : .transitionFlipFromRight
        let options: UIView.AnimationOptions = [
            direction,
            .beginFromCurrentState,
            .allowUserInteraction
        ]

        UIView.transition(
            with: view,
            duration: duration,
            options: options,
            animations: nil
        ) { finished in
            completion(finished)
        }
    }

    private func animateBounce(
        on view: UIView,
        duration: TimeInterval,
        completion: @escaping (Bool) -> Void
    ) {
        let baseTransform = view.transform
        let options: UIView.KeyframeAnimationOptions = [
            .calculationModeCubic,
            .beginFromCurrentState,
            .allowUserInteraction
        ]

        UIView.animateKeyframes(
            withDuration: min(duration, 0.65),
            delay: 0,
            options: options
        ) {
            UIView.addKeyframe(withRelativeStartTime: 0.00, relativeDuration: 0.24) {
                view.transform = baseTransform.scaledBy(x: 0.74, y: 0.74)
            }
            UIView.addKeyframe(withRelativeStartTime: 0.24, relativeDuration: 0.32) {
                view.transform = baseTransform.scaledBy(x: 1.20, y: 1.20)
            }
            UIView.addKeyframe(withRelativeStartTime: 0.56, relativeDuration: 0.20) {
                view.transform = baseTransform.scaledBy(x: 0.94, y: 0.94)
            }
            UIView.addKeyframe(withRelativeStartTime: 0.76, relativeDuration: 0.24) {
                view.transform = baseTransform
            }
        } completion: { finished in
            completion(finished)
        }
    }

    private func animateWiggle(
        on view: UIView,
        duration: TimeInterval,
        completion: @escaping (Bool) -> Void
    ) {
        let baseTransform = view.transform
        let angle = CGFloat.pi / 12.0
        let options: UIView.KeyframeAnimationOptions = [
            .calculationModeCubic,
            .beginFromCurrentState,
            .allowUserInteraction
        ]

        UIView.animateKeyframes(
            withDuration: min(duration, 0.75),
            delay: 0,
            options: options
        ) {
            UIView.addKeyframe(withRelativeStartTime: 0.00, relativeDuration: 0.20) {
                view.transform = baseTransform.rotated(by: angle)
            }
            UIView.addKeyframe(withRelativeStartTime: 0.20, relativeDuration: 0.25) {
                view.transform = baseTransform.rotated(by: -angle)
            }
            UIView.addKeyframe(withRelativeStartTime: 0.45, relativeDuration: 0.22) {
                view.transform = baseTransform.rotated(by: angle * 0.60)
            }
            UIView.addKeyframe(withRelativeStartTime: 0.67, relativeDuration: 0.33) {
                view.transform = baseTransform
            }
        } completion: { finished in
            completion(finished)
        }
    }

    private func animateRotation(
        on view: UIView,
        duration: TimeInterval,
        completion: @escaping (Bool) -> Void
    ) {
        let baseTransform = view.transform
        let direction: CGFloat = Bool.random() ? 1.0 : -1.0
        let angle = direction * CGFloat.pi / 6.0
        let options: UIView.KeyframeAnimationOptions = [
            .calculationModeCubic,
            .beginFromCurrentState,
            .allowUserInteraction
        ]

        UIView.animateKeyframes(
            withDuration: min(duration, 0.80),
            delay: 0,
            options: options
        ) {
            UIView.addKeyframe(withRelativeStartTime: 0.00, relativeDuration: 0.45) {
                view.transform = baseTransform
                    .rotated(by: angle)
                    .scaledBy(x: 1.08, y: 1.08)
            }
            UIView.addKeyframe(withRelativeStartTime: 0.45, relativeDuration: 0.55) {
                view.transform = baseTransform
            }
        } completion: { finished in
            completion(finished)
        }
    }

    private func animateHorizontalShake(
        on view: UIView,
        duration: TimeInterval,
        completion: @escaping (Bool) -> Void
    ) {
        let baseTransform = view.transform
        let horizontalOffset: CGFloat = 10.0
        let options: UIView.KeyframeAnimationOptions = [
            .calculationModeCubic,
            .beginFromCurrentState,
            .allowUserInteraction
        ]

        UIView.animateKeyframes(
            withDuration: min(duration, 0.70),
            delay: 0,
            options: options
        ) {
            UIView.addKeyframe(withRelativeStartTime: 0.00, relativeDuration: 0.18) {
                view.transform = baseTransform.translatedBy(x: horizontalOffset, y: 0)
            }
            UIView.addKeyframe(withRelativeStartTime: 0.18, relativeDuration: 0.20) {
                view.transform = baseTransform.translatedBy(x: -horizontalOffset, y: 0)
            }
            UIView.addKeyframe(withRelativeStartTime: 0.38, relativeDuration: 0.18) {
                view.transform = baseTransform.translatedBy(x: horizontalOffset * 0.70, y: 0)
            }
            UIView.addKeyframe(withRelativeStartTime: 0.56, relativeDuration: 0.18) {
                view.transform = baseTransform.translatedBy(x: -horizontalOffset * 0.45, y: 0)
            }
            UIView.addKeyframe(withRelativeStartTime: 0.74, relativeDuration: 0.26) {
                view.transform = baseTransform
            }
        } completion: { finished in
            completion(finished)
        }
    }

    private func animateJumpLanding(
        on view: UIView,
        duration: TimeInterval,
        completion: @escaping (Bool) -> Void
    ) {
        let baseTransform = view.transform
        let jumpHeight: CGFloat = 12.0
        let landingDepth: CGFloat = 3.0
        let options: UIView.KeyframeAnimationOptions = [
            .calculationModeCubic,
            .beginFromCurrentState,
            .allowUserInteraction
        ]

        UIView.animateKeyframes(
            withDuration: min(duration, 0.75),
            delay: 0,
            options: options
        ) {
            UIView.addKeyframe(withRelativeStartTime: 0.00, relativeDuration: 0.42) {
                view.transform = baseTransform.translatedBy(x: 0, y: -jumpHeight)
                    .scaledBy(x: 1.08, y: 1.08)
            }
            UIView.addKeyframe(withRelativeStartTime: 0.42, relativeDuration: 0.26) {
                view.transform = baseTransform.translatedBy(x: 0, y: landingDepth)
                    .scaledBy(x: 1.10, y: 0.88)
            }
            UIView.addKeyframe(withRelativeStartTime: 0.68, relativeDuration: 0.16) {
                view.transform = baseTransform
                    .translatedBy(x: 0, y: -2.0)
                    .scaledBy(x: 0.98, y: 1.04)
            }
            UIView.addKeyframe(withRelativeStartTime: 0.84, relativeDuration: 0.16) {
                view.transform = baseTransform
            }
        } completion: { finished in
            completion(finished)
        }
    }

    private func animateJelly(
        on view: UIView,
        duration: TimeInterval,
        completion: @escaping (Bool) -> Void
    ) {
        let baseTransform = view.transform
        let options: UIView.KeyframeAnimationOptions = [
            .calculationModeCubic,
            .beginFromCurrentState,
            .allowUserInteraction
        ]

        UIView.animateKeyframes(
            withDuration: min(duration, 0.70),
            delay: 0,
            options: options
        ) {
            UIView.addKeyframe(withRelativeStartTime: 0.00, relativeDuration: 0.28) {
                view.transform = baseTransform.scaledBy(x: 1.16, y: 0.84)
            }
            UIView.addKeyframe(withRelativeStartTime: 0.28, relativeDuration: 0.30) {
                view.transform = baseTransform.scaledBy(x: 0.88, y: 1.14)
            }
            UIView.addKeyframe(withRelativeStartTime: 0.58, relativeDuration: 0.20) {
                view.transform = baseTransform.scaledBy(x: 1.06, y: 0.95)
            }
            UIView.addKeyframe(withRelativeStartTime: 0.78, relativeDuration: 0.22) {
                view.transform = baseTransform
            }
        } completion: { finished in
            completion(finished)
        }
    }

    private func animateOrbitSpiral(
        on view: UIView,
        duration: TimeInterval,
        completion: @escaping (Bool) -> Void
    ) {
        let baseTransform = view.transform
        let orbitRadiusX: CGFloat = 16.0
        let orbitRadiusY: CGFloat = 13.0
        let orbitAngle = CGFloat.pi / 7.0
        let options: UIView.KeyframeAnimationOptions = [
            .calculationModeCubic,
            .beginFromCurrentState,
            .allowUserInteraction
        ]

        UIView.animateKeyframes(
            withDuration: min(duration, 0.90),
            delay: 0,
            options: options
        ) {
            UIView.addKeyframe(withRelativeStartTime: 0.00, relativeDuration: 0.20) {
                view.transform = baseTransform
                    .translatedBy(x: orbitRadiusX, y: -orbitRadiusY)
                    .rotated(by: orbitAngle)
                    .scaledBy(x: 1.10, y: 1.10)
            }
            UIView.addKeyframe(withRelativeStartTime: 0.20, relativeDuration: 0.22) {
                view.transform = baseTransform
                    .translatedBy(x: -orbitRadiusX * 0.72, y: -orbitRadiusY * 0.82)
                    .rotated(by: -orbitAngle * 0.72)
                    .scaledBy(x: 0.96, y: 1.06)
            }
            UIView.addKeyframe(withRelativeStartTime: 0.42, relativeDuration: 0.22) {
                view.transform = baseTransform
                    .translatedBy(x: -orbitRadiusX, y: orbitRadiusY)
                    .rotated(by: -orbitAngle * 1.25)
                    .scaledBy(x: 0.92, y: 0.92)
            }
            UIView.addKeyframe(withRelativeStartTime: 0.64, relativeDuration: 0.18) {
                view.transform = baseTransform
                    .translatedBy(x: orbitRadiusX * 0.56, y: orbitRadiusY * 0.62)
                    .rotated(by: orbitAngle * 0.62)
                    .scaledBy(x: 1.04, y: 0.98)
            }
            UIView.addKeyframe(withRelativeStartTime: 0.82, relativeDuration: 0.18) {
                view.transform = baseTransform
                    .translatedBy(x: orbitRadiusX * 0.24, y: -orbitRadiusY * 0.20)
                    .rotated(by: -orbitAngle * 0.24)
                    .scaledBy(x: 1.02, y: 1.01)
            }
            UIView.addKeyframe(withRelativeStartTime: 0.94, relativeDuration: 0.06) {
                view.transform = baseTransform
            }
        } completion: { finished in
            completion(finished)
        }
    }

    private func animateFlutterLeaf(
        on view: UIView,
        duration: TimeInterval,
        completion: @escaping (Bool) -> Void
    ) {
        let baseTransform = view.transform
        let leafOffsetX: CGFloat = 12.0
        let leafOffsetY: CGFloat = 8.0
        let leafAngle = CGFloat.pi / 10.0
        let options: UIView.KeyframeAnimationOptions = [
            .calculationModeCubic,
            .beginFromCurrentState,
            .allowUserInteraction
        ]

        UIView.animateKeyframes(
            withDuration: min(duration, 0.85),
            delay: 0,
            options: options
        ) {
            UIView.addKeyframe(withRelativeStartTime: 0.00, relativeDuration: 0.18) {
                view.transform = baseTransform
                    .translatedBy(x: -leafOffsetX, y: -leafOffsetY)
                    .rotated(by: -leafAngle)
                    .scaledBy(x: 1.06, y: 0.95)
            }
            UIView.addKeyframe(withRelativeStartTime: 0.18, relativeDuration: 0.22) {
                view.transform = baseTransform
                    .translatedBy(x: leafOffsetX, y: leafOffsetY)
                    .rotated(by: leafAngle)
                    .scaledBy(x: 0.96, y: 1.04)
            }
            UIView.addKeyframe(withRelativeStartTime: 0.40, relativeDuration: 0.20) {
                view.transform = baseTransform
                    .translatedBy(x: -leafOffsetX * 0.62, y: leafOffsetY * 0.52)
                    .rotated(by: -leafAngle * 0.58)
                    .scaledBy(x: 1.04, y: 0.97)
            }
            UIView.addKeyframe(withRelativeStartTime: 0.60, relativeDuration: 0.18) {
                view.transform = baseTransform
                    .translatedBy(x: leafOffsetX * 0.38, y: -leafOffsetY * 0.30)
                    .rotated(by: leafAngle * 0.32)
                    .scaledBy(x: 0.99, y: 1.02)
            }
            UIView.addKeyframe(withRelativeStartTime: 0.78, relativeDuration: 0.22) {
                view.transform = baseTransform
            }
        } completion: { finished in
            completion(finished)
        }
    }

    private func animateInfinityDrift(
        on view: UIView,
        duration: TimeInterval,
        completion: @escaping (Bool) -> Void
    ) {
        let baseTransform = view.transform
        let infinityOffsetX: CGFloat = 14.0
        let infinityOffsetY: CGFloat = 8.0
        let options: UIView.KeyframeAnimationOptions = [
            .calculationModeCubic,
            .beginFromCurrentState,
            .allowUserInteraction
        ]

        UIView.animateKeyframes(
            withDuration: min(duration, 0.95),
            delay: 0,
            options: options
        ) {
            UIView.addKeyframe(withRelativeStartTime: 0.000, relativeDuration: 0.125) {
                view.transform = baseTransform
                    .translatedBy(x: infinityOffsetX * 0.72, y: -infinityOffsetY)
            }
            UIView.addKeyframe(withRelativeStartTime: 0.125, relativeDuration: 0.125) {
                view.transform = baseTransform
                    .translatedBy(x: infinityOffsetX, y: 0)
            }
            UIView.addKeyframe(withRelativeStartTime: 0.250, relativeDuration: 0.125) {
                view.transform = baseTransform
                    .translatedBy(x: infinityOffsetX * 0.72, y: infinityOffsetY)
            }
            UIView.addKeyframe(withRelativeStartTime: 0.375, relativeDuration: 0.125) {
                view.transform = baseTransform
            }
            UIView.addKeyframe(withRelativeStartTime: 0.500, relativeDuration: 0.125) {
                view.transform = baseTransform
                    .translatedBy(x: -infinityOffsetX * 0.72, y: -infinityOffsetY)
            }
            UIView.addKeyframe(withRelativeStartTime: 0.625, relativeDuration: 0.125) {
                view.transform = baseTransform
                    .translatedBy(x: -infinityOffsetX, y: 0)
            }
            UIView.addKeyframe(withRelativeStartTime: 0.750, relativeDuration: 0.125) {
                view.transform = baseTransform
                    .translatedBy(x: -infinityOffsetX * 0.72, y: infinityOffsetY)
            }
            UIView.addKeyframe(withRelativeStartTime: 0.875, relativeDuration: 0.125) {
                view.transform = baseTransform
            }
        } completion: { finished in
            view.transform = baseTransform
            completion(finished)
        }
    }

    private func animateRocketLaunch(
        on view: UIView,
        duration: TimeInterval,
        completion: @escaping (Bool) -> Void
    ) {
        let baseTransform = view.transform
        let launchHeight: CGFloat = 30.0
        let landingDepth: CGFloat = 5.0
        let launchAngle: CGFloat = Bool.random()
            ? CGFloat.pi / 18.0
            : -CGFloat.pi / 18.0
        let options: UIView.KeyframeAnimationOptions = [
            .calculationModeCubic,
            .beginFromCurrentState,
            .allowUserInteraction
        ]

        UIView.animateKeyframes(
            withDuration: min(duration, 1.05),
            delay: 0,
            options: options
        ) {
            UIView.addKeyframe(withRelativeStartTime: 0.00, relativeDuration: 0.14) {
                view.transform = baseTransform
                    .translatedBy(x: 0, y: 4.0)
                    .scaledBy(x: 1.22, y: 0.76)
            }
            UIView.addKeyframe(withRelativeStartTime: 0.14, relativeDuration: 0.26) {
                view.transform = baseTransform
                    .translatedBy(x: 0, y: -launchHeight * 0.65)
                    .rotated(by: launchAngle * 0.65)
                    .scaledBy(x: 1.08, y: 0.94)
            }
            UIView.addKeyframe(withRelativeStartTime: 0.40, relativeDuration: 0.22) {
                view.transform = baseTransform
                    .translatedBy(x: 0, y: -launchHeight)
                    .rotated(by: launchAngle)
                    .scaledBy(x: 1.14, y: 1.08)
            }
            UIView.addKeyframe(withRelativeStartTime: 0.62, relativeDuration: 0.18) {
                view.transform = baseTransform
                    .translatedBy(x: 0, y: landingDepth)
                    .rotated(by: launchAngle * 0.35)
                    .scaledBy(x: 1.28, y: 0.72)
            }
            UIView.addKeyframe(withRelativeStartTime: 0.80, relativeDuration: 0.12) {
                view.transform = baseTransform
                    .translatedBy(x: 0, y: -3.0)
                    .scaledBy(x: 0.96, y: 1.08)
            }
            UIView.addKeyframe(withRelativeStartTime: 0.92, relativeDuration: 0.08) {
                view.transform = baseTransform
            }
        } completion: { finished in
            view.transform = baseTransform
            completion(finished)
        }
    }

    private func animateSlingshot(
        on view: UIView,
        duration: TimeInterval,
        completion: @escaping (Bool) -> Void
    ) {
        let baseTransform = view.transform
        let direction: CGFloat = Bool.random() ? 1.0 : -1.0
        let verticalDirection: CGFloat = Bool.random() ? 1.0 : -1.0
        let slingshotOffsetX: CGFloat = 30.0
        let slingshotOffsetY: CGFloat = 14.0
        let slingshotAngle = direction * CGFloat.pi / 5.0
        let options: UIView.KeyframeAnimationOptions = [
            .calculationModeCubic,
            .beginFromCurrentState,
            .allowUserInteraction
        ]

        UIView.animateKeyframes(
            withDuration: min(duration, 1.00),
            delay: 0,
            options: options
        ) {
            UIView.addKeyframe(withRelativeStartTime: 0.00, relativeDuration: 0.16) {
                view.transform = baseTransform
                    .translatedBy(
                        x: -direction * slingshotOffsetX * 0.42,
                        y: -verticalDirection * slingshotOffsetY * 0.45
                    )
                    .rotated(by: -slingshotAngle * 0.45)
                    .scaledBy(x: 0.86, y: 1.10)
            }
            UIView.addKeyframe(withRelativeStartTime: 0.16, relativeDuration: 0.30) {
                view.transform = baseTransform
                    .translatedBy(
                        x: direction * slingshotOffsetX,
                        y: verticalDirection * slingshotOffsetY
                    )
                    .rotated(by: slingshotAngle)
                    .scaledBy(x: 1.18, y: 0.86)
            }
            UIView.addKeyframe(withRelativeStartTime: 0.46, relativeDuration: 0.22) {
                view.transform = baseTransform
                    .translatedBy(
                        x: -direction * slingshotOffsetX * 0.48,
                        y: -verticalDirection * slingshotOffsetY * 0.30
                    )
                    .rotated(by: -slingshotAngle * 0.48)
                    .scaledBy(x: 0.92, y: 1.08)
            }
            UIView.addKeyframe(withRelativeStartTime: 0.68, relativeDuration: 0.17) {
                view.transform = baseTransform
                    .translatedBy(
                        x: direction * slingshotOffsetX * 0.16,
                        y: verticalDirection * slingshotOffsetY * 0.10
                    )
                    .rotated(by: slingshotAngle * 0.18)
                    .scaledBy(x: 1.05, y: 0.97)
            }
            UIView.addKeyframe(withRelativeStartTime: 0.85, relativeDuration: 0.15) {
                view.transform = baseTransform
            }
        } completion: { finished in
            view.transform = baseTransform
            completion(finished)
        }
    }

    private func finishAnimation(token: UInt64, expectedView: UIView?) {
        precondition(Thread.isMainThread)
        guard isAnimating, animationSequence == token else {
            return
        }

        if let expectedView = expectedView,
           let activeAnimationView = activeAnimationView,
           activeAnimationView !== expectedView {
            return
        }

        activeAnimationView = nil
        isAnimating = false
    }

    private static func nextAttemptDelay() -> TimeInterval {
        return TimeInterval(Int.random(in: 50...409)) / 100.0
    }

    private static func nextAnimationDuration() -> TimeInterval {
        return TimeInterval(Int.random(in: 5...14)) / 10.0
    }
}
