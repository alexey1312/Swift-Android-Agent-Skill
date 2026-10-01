import Foundation

/// Pushes balance changes for one account. Stands in for the app's websocket client.
public final class BalanceSocket: @unchecked Sendable {
    public static let shared = BalanceSocket()
    private var listeners: [UUID: (String, Int) -> Void] = [:]

    public func subscribe(_ listener: @escaping (String, Int) -> Void) -> UUID {
        let token = UUID()
        listeners[token] = listener
        return token
    }

    public func unsubscribe(_ token: UUID) {
        listeners[token] = nil
    }

    public var listenerCount: Int { listeners.count }
}
