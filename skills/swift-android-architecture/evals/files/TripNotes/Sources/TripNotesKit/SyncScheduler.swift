import Foundation

/// Pings the sync endpoint every few minutes while the app is open.
public final class SyncScheduler: NSObject {
    private var timer: Timer?
    private let onTick: () -> Void

    public init(onTick: @escaping () -> Void) {
        self.onTick = onTick
        super.init()
    }

    public func start() {
        timer = Timer.scheduledTimer(timeInterval: 300, target: self, selector: #selector(tick), userInfo: nil, repeats: true)
    }

    public func stop() {
        timer?.invalidate()
        timer = nil
    }

    @objc private func tick() {
        onTick()
    }
}
