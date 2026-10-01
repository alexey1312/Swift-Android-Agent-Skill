import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif
import SharedCore
import XCTest

/// Foundation behavior the core relies on. Run on an Android emulator, these
/// show that the pieces are present at runtime, not only at compile time.
final class FoundationRuntimeTests: XCTestCase {
    func testJSONRoundTripKeepsISO8601Dates() throws {
        let data = try JSONCoding.encoder().encode(Market.rain)
        let json = String(decoding: data, as: UTF8.self)

        XCTAssertTrue(json.contains(#""closesAt":"2026-11-03T12:00:00Z""#), json)
        XCTAssertEqual(try JSONCoding.decoder().decode(Market.self, from: data), .rain)
    }

    func testDecodesTheBackendShape() throws {
        let body = #"[{"id":"m2","question":"Will it snow in Oslo?","probability":0.75,"closesAt":"2026-11-03T12:00:00Z"}]"#

        let markets = try JSONCoding.decoder().decode([Market].self, from: Data(body.utf8))

        XCTAssertEqual(markets, [.snow])
    }

    func testTemporaryFileRoundTrip() throws {
        let files = FileManager.default
        let directory = files.temporaryDirectory.appending(path: "SharedCoreTests-\(UUID().uuidString)", directoryHint: .isDirectory)
        try files.createDirectory(at: directory, withIntermediateDirectories: true)
        defer { try? files.removeItem(at: directory) }
        let file = directory.appending(path: "markets.json")

        try JSONCoding.encoder().encode([Market.rain]).write(to: file, options: .atomic)
        let restored = try JSONCoding.decoder().decode([Market].self, from: Data(contentsOf: file))

        XCTAssertEqual(restored, [.rain])
        XCTAssertTrue(files.fileExists(atPath: file.path(percentEncoded: false)))
    }

    func testDateFormattingUsesLocaleData() throws {
        let formatter = DateFormatter()
        formatter.timeZone = try XCTUnwrap(TimeZone(secondsFromGMT: 0))
        formatter.dateFormat = "d MMMM yyyy"

        formatter.locale = Locale(identifier: "en_US_POSIX")
        XCTAssertEqual(formatter.string(from: closingDate), "3 November 2026")
        formatter.locale = Locale(identifier: "fr_FR")
        XCTAssertEqual(formatter.string(from: closingDate), "3 novembre 2026")
        XCTAssertEqual(Locale(identifier: "de_DE").decimalSeparator, ",")
    }

    func testMarketsRequestIsBuiltWithoutTheNetwork() throws {
        let api = MarketsAPI(baseURL: try XCTUnwrap(URL(string: "https://api.example.com/v1")))

        let request = api.marketsRequest(limit: 20)

        XCTAssertEqual(request.url?.absoluteString, "https://api.example.com/v1/markets?limit=20")
        XCTAssertEqual(request.httpMethod, "GET")
        XCTAssertEqual(request.value(forHTTPHeaderField: "Accept"), "application/json")
        XCTAssertEqual(request.timeoutInterval, 15)
    }
}
