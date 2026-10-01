import Combine
import Foundation
import Observation

/// Live prices for the watchlist screen. The iOS app and the Compose app both show it.
@Observable
public final class PriceBoard {
    public private(set) var prices: [String: Price] = [:]
    public private(set) var isConnected = false

    private let subject = PassthroughSubject<Price, Never>()

    /// The Kotlin team wants to collect this in a coroutine.
    public var priceUpdates: AnyPublisher<Price, Never> {
        subject.eraseToAnyPublisher()
    }

    public init() {}

    public func connect() {
        isConnected = true
    }

    public func receive(_ price: Price) {
        prices[price.symbol] = price
        subject.send(price)
    }

    /// Called by the order ticket on both platforms.
    public func quote(
        symbol: String,
        quantity: Int,
        side: String,
        limitCents: Int?,
        expiresAt: Date?,
        completion: @escaping (String, Int, Int, Bool, Date, String?) -> Void
    ) {
        let price = prices[symbol]?.cents ?? 0
        completion(symbol, quantity, price * quantity, price > 0, Date(), nil)
    }

    #if !SKIP
    /// iOS only: a light haptic when a watched price crosses its alert.
    public func playAlertHaptic() {
        // UIImpactFeedbackGenerator(style: .light).impactOccurred()
    }
    #endif
}
