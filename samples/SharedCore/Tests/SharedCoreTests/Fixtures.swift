import Foundation
import SharedCore

/// 2026-11-03T12:00:00Z
let closingDate = Date(timeIntervalSince1970: 1_793_707_200)

extension Market {
    static let rain = Market(id: "m1", question: "Will it rain in Lisbon?", probability: 0.25, closesAt: closingDate)
    static let snow = Market(id: "m2", question: "Will it snow in Oslo?", probability: 0.75, closesAt: closingDate)
}

struct StubMarkets: MarketsLoading {
    var result: Result<[Market], any Error>

    func markets() async throws -> [Market] {
        try result.get()
    }
}

struct Offline: Error {}

/// Collects what navigation callbacks receive: a main-actor class, so the
/// callbacks capture no mutable local state.
@MainActor
final class Recorder<Value> {
    private(set) var values: [Value] = []

    func record(_ value: Value) {
        values.append(value)
    }
}
