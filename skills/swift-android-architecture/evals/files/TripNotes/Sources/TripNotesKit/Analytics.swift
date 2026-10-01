import Foundation

public final class Analytics: @unchecked Sendable {
    public static let shared = Analytics()

    public func track(_ event: String, _ properties: [String: String] = [:]) {
        print("[analytics] \(event) \(properties)")
    }
}
