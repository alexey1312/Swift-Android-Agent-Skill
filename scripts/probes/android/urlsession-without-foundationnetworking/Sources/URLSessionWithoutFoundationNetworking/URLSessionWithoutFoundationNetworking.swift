// Does URLSession resolve on Android with only `import Foundation`?
import Foundation

public func fetch(_ url: URL) async throws -> Data {
    let (data, _) = try await URLSession.shared.data(from: url)
    return data
}
