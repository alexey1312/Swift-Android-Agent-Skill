import Foundation
import XCTest
@testable import TripNotesKit

final class TripTests: XCTestCase {
    func testRoundTripsThroughJSON() throws {
        let trip = Trip(title: "Lisbon", startsOn: Date(timeIntervalSince1970: 1_800_000_000), latitude: 38.72, longitude: -9.14)
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        XCTAssertEqual(try decoder.decode(Trip.self, from: encoder.encode(trip)), trip)
    }
}
