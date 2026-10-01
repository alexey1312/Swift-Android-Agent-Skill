import Observation

/// The market detail screen: one market and a purchase through the injected payments client.
@MainActor
@Observable
public final class MarketDetailViewModel {
    public enum Input: Equatable, Sendable {
        case buy(amountCents: Int)
        case close
    }

    public enum Purchase: Equatable, Sendable {
        case idle
        case inProgress
        case completed(Receipt)
        case failed(String)
    }

    public let market: Market
    public private(set) var purchase: Purchase = .idle

    @ObservationIgnored private let payments: any PaymentsClient
    @ObservationIgnored private let analytics: any AnalyticsClient
    @ObservationIgnored private let close: @MainActor () -> Void

    public init(
        market: Market,
        payments: any PaymentsClient,
        analytics: any AnalyticsClient,
        close: @escaping @MainActor () -> Void
    ) {
        self.market = market
        self.payments = payments
        self.analytics = analytics
        self.close = close
    }

    @discardableResult
    public func send(_ input: Input) -> Task<Void, Never>? {
        switch input {
        case .buy(let amountCents):
            guard purchase != .inProgress, amountCents > 0 else { return nil }
            purchase = .inProgress
            return Task { await buy(amountCents: amountCents) }
        case .close:
            close()
            return nil
        }
    }

    private func buy(amountCents: Int) async {
        do {
            let receipt = try await payments.purchase(marketID: market.id, amountCents: amountCents)
            purchase = .completed(receipt)
            analytics.track("purchase_completed")
        } catch {
            purchase = .failed("The purchase did not go through.")
        }
    }
}
