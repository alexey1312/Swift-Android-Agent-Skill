import SwiftUI
import TripNotesKit

public struct TripListView: View {
    @StateObject private var model: TripListViewModel

    public init(client: APIClient) {
        _model = StateObject(wrappedValue: TripListViewModel(client: client))
    }

    public var body: some View {
        NavigationStack {
            List(model.visibleTrips) { trip in
                NavigationLink(value: trip) {
                    Text(trip.title)
                }
            }
            .navigationDestination(for: Trip.self) { trip in
                TripMapView(trip: trip)
            }
            .searchable(text: $model.searchText)
            .overlay { if model.isLoading { ProgressView() } }
            .task { await model.load() }
        }
    }
}
