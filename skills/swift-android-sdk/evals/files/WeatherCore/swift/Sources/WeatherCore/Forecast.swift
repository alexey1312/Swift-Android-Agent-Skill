import Foundation
import Observation

public struct Reading: Codable, Sendable {
    public let celsius: Double
    public let at: Date
}

@Observable
public final class Forecast {
    public private(set) var readings: [Reading] = []

    public init() {}

    public func ingest(json: String) throws {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        readings = try decoder.decode([Reading].self, from: Data(json.utf8))
    }

    public var average: Double {
        readings.isEmpty ? 0 : readings.map(\.celsius).reduce(0, +) / Double(readings.count)
    }
}

@_cdecl("Java_com_example_weather_WeatherCore_average")
public func weatherAverage(_ env: UnsafeMutableRawPointer?, _ clazz: UnsafeMutableRawPointer?) -> Double {
    Forecast().average
}
