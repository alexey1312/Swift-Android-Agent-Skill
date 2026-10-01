import Foundation

public struct Note: Codable, Identifiable, Hashable, Sendable {
    public let id: UUID
    public var title: String
    public var body: String
    public var updatedAt: Date

    public init(id: UUID = UUID(), title: String, body: String, updatedAt: Date = .now) {
        self.id = id
        self.title = title
        self.body = body
        self.updatedAt = updatedAt
    }
}

public protocol NoteStore: Sendable {
    func all() async throws -> [Note]
    func save(_ note: Note) async throws
}
