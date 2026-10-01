import Foundation

public struct Trip: Codable, Identifiable, Hashable, Sendable {
    public let id: UUID
    public var title: String
    public var startsOn: Date
    public var latitude: Double
    public var longitude: Double
    public var notes: [String]

    public init(id: UUID = UUID(), title: String, startsOn: Date, latitude: Double, longitude: Double, notes: [String] = []) {
        self.id = id
        self.title = title
        self.startsOn = startsOn
        self.latitude = latitude
        self.longitude = longitude
        self.notes = notes
    }
}
