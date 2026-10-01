import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

/// Where markets come from. View models see only this protocol,
/// so tests and previews never touch the network.
public protocol MarketsLoading: Sendable {
    func markets() async throws -> [Market]
}

public enum APIError: Error, Equatable {
    case notHTTP
    case status(Int)
}

/// The backend client. Outside Apple platforms `URLSession` lives in
/// FoundationNetworking, hence the conditional import above.
public struct MarketsAPI: MarketsLoading {
    public let baseURL: URL
    private let session: URLSession

    public init(baseURL: URL, session: URLSession = .shared) {
        self.baseURL = baseURL
        self.session = session
    }

    /// Built apart from `markets()` so a test can check it without a network.
    public func marketsRequest(limit: Int = 50) -> URLRequest {
        let url = baseURL
            .appending(path: "markets")
            .appending(queryItems: [URLQueryItem(name: "limit", value: String(limit))])
        var request = URLRequest(url: url, timeoutInterval: 15)
        request.httpMethod = "GET"
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        return request
    }

    public func markets() async throws -> [Market] {
        let (data, response) = try await session.data(for: marketsRequest())
        guard let http = response as? HTTPURLResponse else { throw APIError.notHTTP }
        guard (200..<300).contains(http.statusCode) else { throw APIError.status(http.statusCode) }
        return try JSONCoding.decoder().decode([Market].self, from: data)
    }
}
