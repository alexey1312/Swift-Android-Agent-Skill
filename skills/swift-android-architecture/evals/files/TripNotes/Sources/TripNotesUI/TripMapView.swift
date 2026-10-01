import MapKit
import SwiftUI
import TripNotesKit

struct TripMapView: View {
    let trip: Trip

    var body: some View {
        Map(initialPosition: .region(MKCoordinateRegion(
            center: CLLocationCoordinate2D(latitude: trip.latitude, longitude: trip.longitude),
            span: MKCoordinateSpan(latitudeDelta: 0.2, longitudeDelta: 0.2)
        )))
        .navigationTitle(trip.title)
        .toolbar { AddToWalletButton(trip: trip) }
    }
}
