import Observation

/// The market list screen. SwiftUI renders it on iOS; on Android a Compose screen
/// reads the same state through a bridge and sends the same inputs.
@MainActor
@Observable
public final class MarketListViewModel {
    public enum Input: Equatable, Sendable {
        case appeared
        case refresh
        case select(Market.ID)
        case dismissError
    }

    public private(set) var markets: [Market] = []
    public private(set) var isLoading = false
    public private(set) var errorMessage: String?

    @ObservationIgnored private let api: any MarketsLoading
    @ObservationIgnored private let analytics: any AnalyticsClient
    @ObservationIgnored private let openMarket: @MainActor (Market) -> Void
    @ObservationIgnored private var loading: Task<Void, Never>?

    /// Navigation is a callback: each platform decides what opening a market means.
    public init(
        api: any MarketsLoading,
        analytics: any AnalyticsClient,
        openMarket: @escaping @MainActor (Market) -> Void
    ) {
        self.api = api
        self.analytics = analytics
        self.openMarket = openMarket
    }

    /// Handles one input. Work that outlives the call comes back as a task
    /// so tests can await it; UI code ignores the result.
    @discardableResult
    public func send(_ input: Input) -> Task<Void, Never>? {
        switch input {
        case .appeared where !markets.isEmpty:
            return nil
        case .appeared, .refresh:
            loading?.cancel()
            isLoading = true
            errorMessage = nil
            let task = Task { await load() }
            loading = task
            return task
        case .select(let id):
            guard let market = markets.first(where: { $0.id == id }) else { return nil }
            analytics.track("market_opened")
            openMarket(market)
            return nil
        case .dismissError:
            errorMessage = nil
            return nil
        }
    }

    private func load() async {
        do {
            let loaded = try await api.markets()
            guard !Task.isCancelled else { return }
            markets = loaded
            analytics.track("markets_loaded")
        } catch is CancellationError {
            return
        } catch {
            errorMessage = "Markets could not be loaded."
        }
        isLoading = false
    }
}
