import Foundation

/// A market as the backend sends it. The domain is invented for the sample.
public struct Market: Codable, Equatable, Identifiable, Sendable {
    public let id: String
    public let question: String
    /// The chance of "yes", from 0 to 1.
    public let probability: Double
    public let closesAt: Date

    public init(id: String, question: String, probability: Double, closesAt: Date) {
        self.id = id
        self.question = question
        self.probability = probability
        self.closesAt = closesAt
    }
}

/// What a completed purchase returns.
public struct Receipt: Codable, Equatable, Sendable {
    public let id: String
    public let marketID: Market.ID
    public let amountCents: Int

    public init(id: String, marketID: Market.ID, amountCents: Int) {
        self.id = id
        self.marketID = marketID
        self.amountCents = amountCents
    }
}

/// One JSON configuration for every platform: ISO 8601 dates, stable key order.
public enum JSONCoding {
    public static func decoder() -> JSONDecoder {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        return decoder
    }

    public static func encoder() -> JSONEncoder {
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        encoder.outputFormatting = [.sortedKeys]
        return encoder
    }
}
