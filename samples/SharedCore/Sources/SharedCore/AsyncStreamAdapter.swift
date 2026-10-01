import Foundation

extension AsyncStream where Element: Sendable {
    /// Turns a callback API into a stream. `subscribe` registers the handler and
    /// returns the call that unregisters it; that call runs when the stream ends,
    /// including when the consuming task is cancelled.
    /// Hand the Kotlin side a stream like this one, not a Combine publisher.
    public static func observing(
        bufferingPolicy: Continuation.BufferingPolicy = .unbounded,
        _ subscribe: (@escaping @Sendable (Element) -> Void) -> @Sendable () -> Void
    ) -> AsyncStream<Element> {
        AsyncStream(bufferingPolicy: bufferingPolicy) { continuation in
            let unsubscribe = subscribe { continuation.yield($0) }
            continuation.onTermination = { _ in unsubscribe() }
        }
    }
}

/// An observer-style API of the kind platform SDKs expose (listeners, delegates),
/// kept in memory so the adapter can be shown and tested.
public final class Broadcaster<Value: Sendable>: @unchecked Sendable {
    private let lock = NSLock()
    private var observers: [Int: @Sendable (Value) -> Void] = [:]
    private var nextID = 0

    public init() {}

    public var observerCount: Int {
        lock.lock()
        defer { lock.unlock() }
        return observers.count
    }

    /// Registers `observer` and returns the closure that unregisters it.
    public func addObserver(_ observer: @escaping @Sendable (Value) -> Void) -> @Sendable () -> Void {
        lock.lock()
        defer { lock.unlock() }
        let id = nextID
        nextID += 1
        observers[id] = observer
        return { [weak self] in self?.removeObserver(id) }
    }

    public func send(_ value: Value) {
        lock.lock()
        let current = Array(observers.values)
        lock.unlock()
        for observer in current {
            observer(value)
        }
    }

    /// Every value sent from now on.
    public func values() -> AsyncStream<Value> {
        .observing { addObserver($0) }
    }

    private func removeObserver(_ id: Int) {
        lock.lock()
        defer { lock.unlock() }
        observers[id] = nil
    }
}
