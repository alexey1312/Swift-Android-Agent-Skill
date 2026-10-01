import Observation
import SharedCore
import XCTest

// Main-actor tests are async: XCTest on Linux and Android wraps async tests,
// which keeps the isolation hop out of the generated test list.
final class MarketListViewModelTests: XCTestCase {
    @MainActor
    func testAppearedLoadsMarketsAndTracksIt() async {
        let analytics = InMemoryAnalytics()
        let model = MarketListViewModel(api: StubMarkets(result: .success([.rain, .snow])), analytics: analytics, openMarket: { _ in })

        await model.send(.appeared)?.value

        XCTAssertEqual(model.markets, [.rain, .snow])
        XCTAssertFalse(model.isLoading)
        XCTAssertNil(model.errorMessage)
        XCTAssertEqual(analytics.events, ["markets_loaded"])
        XCTAssertNil(model.send(.appeared), "a second appearance must not reload")
    }

    @MainActor
    func testFailedLoadShowsAnErrorUntilDismissed() async {
        let model = MarketListViewModel(api: StubMarkets(result: .failure(Offline())), analytics: InMemoryAnalytics(), openMarket: { _ in })

        await model.send(.refresh)?.value
        XCTAssertNotNil(model.errorMessage)
        XCTAssertFalse(model.isLoading)

        model.send(.dismissError)
        XCTAssertNil(model.errorMessage)
    }

    @MainActor
    func testSelectingAMarketCallsTheNavigationCallback() async {
        let analytics = InMemoryAnalytics()
        let opened = Recorder<Market.ID>()
        let model = MarketListViewModel(api: StubMarkets(result: .success([.rain, .snow])), analytics: analytics, openMarket: { opened.record($0.id) })

        await model.send(.appeared)?.value
        model.send(.select("m2"))
        model.send(.select("unknown"))

        XCTAssertEqual(opened.values, ["m2"])
        XCTAssertEqual(analytics.events, ["markets_loaded", "market_opened"])
    }

    @MainActor
    func testObservationTrackingFiresWhenStateChanges() async {
        let model = MarketListViewModel(api: StubMarkets(result: .success([.rain])), analytics: InMemoryAnalytics(), openMarket: { _ in })
        let changed = expectation(description: "markets changed")

        withObservationTracking {
            _ = model.markets
        } onChange: {
            changed.fulfill()
        }
        await model.send(.appeared)?.value

        await fulfillment(of: [changed], timeout: 2)
        XCTAssertEqual(model.markets, [.rain])
    }
}

final class MarketDetailViewModelTests: XCTestCase {
    @MainActor
    func testBuyingStoresTheReceipt() async {
        let payments = InMemoryPayments()
        let analytics = InMemoryAnalytics()
        let model = MarketDetailViewModel(market: .rain, payments: payments, analytics: analytics, close: {})

        await model.send(.buy(amountCents: 500))?.value

        let receipt = Receipt(id: "receipt-1", marketID: "m1", amountCents: 500)
        XCTAssertEqual(model.purchase, .completed(receipt))
        let receipts = await payments.receipts
        XCTAssertEqual(receipts, [receipt])
        XCTAssertEqual(analytics.events, ["purchase_completed"])
    }

    @MainActor
    func testDeclinedPurchaseFails() async {
        let model = MarketDetailViewModel(market: .rain, payments: InMemoryPayments(declines: true), analytics: InMemoryAnalytics(), close: {})

        await model.send(.buy(amountCents: 500))?.value

        guard case .failed = model.purchase else {
            return XCTFail("expected a failed purchase, got \(model.purchase)")
        }
    }

    @MainActor
    func testCloseCallsTheNavigationCallback() async {
        let closed = Recorder<Void>()
        let model = MarketDetailViewModel(market: .rain, payments: InMemoryPayments(), analytics: InMemoryAnalytics(), close: { closed.record(()) })

        XCTAssertNil(model.send(.close))
        XCTAssertNil(model.send(.buy(amountCents: 0)), "a zero amount is ignored")

        XCTAssertEqual(closed.values.count, 1)
        XCTAssertEqual(model.purchase, .idle)
    }
}
