import Foundation

public final class Analytics: @unchecked Sendable {
    public static let shared = Analytics()

    public func track(_ event: String) {
        print("[analytics] \(event)")
    }
}
