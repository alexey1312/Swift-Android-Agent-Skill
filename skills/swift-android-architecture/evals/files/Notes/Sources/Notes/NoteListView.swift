import NotesShared
import SwiftUI

public struct NoteListView: View {
    @StateObject private var model: NoteListViewModel

    public init(store: NoteStore) {
        _model = StateObject(wrappedValue: NoteListViewModel(store: store))
    }

    public var body: some View {
        NavigationStack {
            List(model.matches) { note in
                Text(note.title)
            }
            .searchable(text: $model.query)
            .toolbar {
                Button("Add") { Task { await model.add(title: "Untitled") } }
            }
            .task { await model.load() }
        }
    }
}
