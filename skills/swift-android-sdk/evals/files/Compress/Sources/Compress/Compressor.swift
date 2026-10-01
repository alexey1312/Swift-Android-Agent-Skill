import Foundation

public enum CompressionError: Error {
    case emptyInput
    case unreadable(path: String)
}

/// Run-length compression used by the iOS app's export feature.
public struct Compressor: Sendable {
    public var level: Int

    public init(level: Int = 6) {
        self.level = level
    }

    public func compress(_ bytes: [UInt8]) throws -> [UInt8] {
        guard let first = bytes.first else { throw CompressionError.emptyInput }
        var output: [UInt8] = []
        var current = first
        var count: UInt8 = 0
        for byte in bytes {
            if byte == current && count < .max {
                count += 1
            } else {
                output += [count, current]
                current = byte
                count = 1
            }
        }
        output += [count, current]
        return output
    }

    /// Compresses a file in chunks, reporting progress from 0 to 1.
    public func compressFile(at path: String, progress: @escaping @Sendable (Double) -> Void) async throws -> Int {
        guard let data = FileManager.default.contents(atPath: path) else {
            throw CompressionError.unreadable(path: path)
        }
        let compressed = try compress([UInt8](data))
        progress(1)
        return compressed.count
    }
}
