import Foundation

/// Services the core calls but each app implements: an analytics SDK,
/// StoreKit on iOS, Play Billing behind a Kotlin bridge on Android.
/// They are passed in through initializers, never reached through a singleton.
public protocol AnalyticsClient: Sendable {
    func track(_ event: String)
}

public protocol PaymentsClient: Sendable {
    func purchase(marketID: Market.ID, amountCents: Int) async throws -> Receipt
}

/// Keeps events in memory, for tests and previews.
public final class InMemoryAnalytics: AnalyticsClient, @unchecked Sendable {
    private let lock = NSLock()
    private var recorded: [String] = []

    public init() {}

    public var events: [String] {
        lock.lock()
        defer { lock.unlock() }
        return recorded
    }

    public func track(_ event: String) {
        lock.lock()
        defer { lock.unlock() }
        recorded.append(event)
    }
}

/// Approves or declines every purchase, for tests and previews.
public actor InMemoryPayments: PaymentsClient {
    public struct Declined: Error, Equatable {}

    public private(set) var receipts: [Receipt] = []
    private let declines: Bool

    public init(declines: Bool = false) {
        self.declines = declines
    }

    public func purchase(marketID: Market.ID, amountCents: Int) async throws -> Receipt {
        if declines { throw Declined() }
        let receipt = Receipt(id: "receipt-\(receipts.count + 1)", marketID: marketID, amountCents: amountCents)
        receipts.append(receipt)
        return receipt
    }
}
