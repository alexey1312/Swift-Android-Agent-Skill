import Combine
import Foundation
import SwiftUI

@MainActor
public final class NoteListViewModel: ObservableObject {
    @Published public private(set) var notes: [Note] = []
    @Published public var query = ""
    @Published public private(set) var matches: [Note] = []

    private let store: NoteStore
    private var cancellables = Set<AnyCancellable>()

    public init(store: NoteStore) {
        self.store = store
        $query
            .debounce(for: .milliseconds(250), scheduler: RunLoop.main)
            .removeDuplicates()
            .sink { [weak self] query in
                guard let self else { return }
                withAnimation { self.matches = self.filter(self.notes, by: query) }
                Analytics.shared.track("search")
            }
            .store(in: &cancellables)
    }

    public func load() async {
        notes = (try? await store.all()) ?? []
        matches = filter(notes, by: query)
        Analytics.shared.track("notes_loaded")
    }

    public func add(title: String) async {
        let note = Note(title: title, body: "")
        try? await store.save(note)
        notes.insert(note, at: 0)
        matches = filter(notes, by: query)
        Analytics.shared.track("note_added")
    }

    private func filter(_ notes: [Note], by query: String) -> [Note] {
        query.isEmpty ? notes : notes.filter { $0.title.localizedCaseInsensitiveContains(query) }
    }
}
