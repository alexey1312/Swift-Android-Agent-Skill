import Foundation

public struct Price: Sendable, Hashable {
    public let symbol: String
    public let cents: Int
    public let at: Date

    public init(symbol: String, cents: Int, at: Date) {
        self.symbol = symbol
        self.cents = cents
        self.at = at
    }
}
