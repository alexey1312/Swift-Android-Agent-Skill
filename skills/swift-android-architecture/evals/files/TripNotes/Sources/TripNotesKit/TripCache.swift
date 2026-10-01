import Foundation

struct TripCache {
    var url: URL {
        FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask)[0].appending(path: "trips.json")
    }

    func save(_ trips: [Trip]) throws {
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        try encoder.encode(trips).write(to: url, options: .atomic)
    }

    func load() throws -> [Trip] {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        return try decoder.decode([Trip].self, from: Data(contentsOf: url))
    }
}
