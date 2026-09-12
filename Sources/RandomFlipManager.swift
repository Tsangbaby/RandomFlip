import Foundation
import UIKit

@MainActor
@objc(RandomFlipManager)
public final class RandomFlipManager: NSObject {
    private static let singleton = RandomFlipManager(environment: SpringBoardEnvironment())

    private static let initialDelay: TimeInterval = 1.5
    private static let requiredConsecutiveReadyTicks = 2

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
        ) { [weak self, weak view] _ in
            self?.finishAnimation(token: token, expectedView: view)
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
