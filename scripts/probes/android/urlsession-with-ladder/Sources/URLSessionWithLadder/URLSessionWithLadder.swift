// Does URLSession resolve on Android behind the FoundationNetworking import ladder?
import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

public func fetch(_ url: URL) async throws -> Data {
    let (data, _) = try await URLSession.shared.data(from: url)
    return data
}
