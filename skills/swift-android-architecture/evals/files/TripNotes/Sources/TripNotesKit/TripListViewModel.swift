import Combine
import Foundation

@MainActor
public final class TripListViewModel: ObservableObject {
    @Published public private(set) var trips: [Trip] = []
    @Published public var searchText = ""
    @Published public private(set) var isLoading = false

    private let client: APIClient
    private var cancellables = Set<AnyCancellable>()

    public init(client: APIClient) {
        self.client = client
        $searchText
            .debounce(for: .milliseconds(300), scheduler: RunLoop.main)
            .sink { text in Analytics.shared.track("search", ["length": "\(text.count)"]) }
            .store(in: &cancellables)
    }

    public var visibleTrips: [Trip] {
        searchText.isEmpty ? trips : trips.filter { $0.title.localizedCaseInsensitiveContains(searchText) }
    }

    public func load() async {
        isLoading = true
        defer { isLoading = false }
        do {
            trips = try await client.trips()
            try? TripCache().save(trips)
        } catch {
            trips = (try? TripCache().load()) ?? []
        }
    }
}
