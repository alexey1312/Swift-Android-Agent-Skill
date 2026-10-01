# View models

A view model in shared code is a plain `@Observable` class:
actions come in through an input enum,
state goes out through observable properties,
and navigation leaves through callbacks the screen provides.
It imports no UIKit and no SwiftUI,
so the same instance can drive SwiftUI and UIKit on iOS and Compose on Android.
That is the shape Polymarket describes for its 120+ shared view models
(Swift Forums › Our Android app is written in Swift, @poly-rob, 2026-08-04, post 1).

## The shape

```swift
// typecheck: shared
import Foundation
import Observation

public protocol AccountClient: Sendable {
    func setNotifications(enabled: Bool) async throws
    func signOut() async throws
}

@MainActor
@Observable
public final class SettingsViewModel {
    public enum Input: Sendable {
        case toggledNotifications(Bool)
        case tappedSignOut
    }

    /// Where the screen goes next; the platform's navigation decides how.
    public struct Navigation {
        public var showSignIn: @MainActor () -> Void
        public init(showSignIn: @escaping @MainActor () -> Void) {
            self.showSignIn = showSignIn
        }
    }

    public private(set) var notificationsOn = false
    public private(set) var isWorking = false
    public private(set) var errorMessage: String?

    private let account: any AccountClient
    private let navigation: Navigation

    public init(account: any AccountClient, navigation: Navigation, notificationsOn: Bool) {
        self.account = account
        self.navigation = navigation
        self.notificationsOn = notificationsOn
    }

    public func send(_ input: Input) {
        switch input {
        case .toggledNotifications(let enabled):
            let previous = notificationsOn
            notificationsOn = enabled
            Task { await run { try await self.account.setNotifications(enabled: enabled) } onFailure: {
                self.notificationsOn = previous
            } }
        case .tappedSignOut:
            Task { await run { try await self.account.signOut(); self.navigation.showSignIn() } onFailure: {} }
        }
    }

    private func run(_ work: @MainActor () async throws -> Void, onFailure: @MainActor () -> Void) async {
        isWorking = true
        defer { isWorking = false }
        do {
            try await work()
            errorMessage = nil
        } catch {
            errorMessage = String(describing: error)
            onFailure()
        }
    }
}
```

- One `send(_:)` entry point keeps every user action visible in one `switch`,
  and makes the view model easy to drive from tests on both platforms.
- State is `private(set)`; screens read it and never write it.
- Navigation callbacks belong to the platform's navigation container;
  the view model only decides *that* something happens next.
- The Polymarket report builds every view model on a small shared base class;
  a protocol or plain composition works as well (*inference*).
- `samples/SharedCore` in this skill's repository holds a tested version of this shape,
  compiled for Android and tested on an emulator in CI (`measured-behavior.md`).

## Rendering the same instance three ways

- **SwiftUI** reads the properties directly; hold the instance in `@State`.
- **UIKit** reads the state where Observation tracks it:
  Polymarket reads it "in `viewWillLayoutSubviews` or `updateProperties`".
  `updateProperties()` is newer than `viewWillLayoutSubviews()`:

```swift
// typecheck: ios26, continues the block above
import UIKit

final class SettingsViewController: UIViewController {
    let model: SettingsViewModel
    private let toggle = UISwitch()

    init(model: SettingsViewModel) {
        self.model = model
        super.init(nibName: nil, bundle: nil)
    }

    required init?(coder: NSCoder) { fatalError("init(coder:) is not supported") }

    override func updateProperties() {
        super.updateProperties()
        toggle.isOn = model.notificationsOn
    }
}
```

- **Compose** reads the bridged properties;
  Skip's observation bridge triggers recomposition when they change (Polymarket report).
  In a native (Fuse) module, every file that defines an `@Observable` must `import SkipFuse`,
  the type must be bridged for a Kotlin UI to use it,
  and a hand-written Compose UI needs a SkipModel dependency
  (skip.dev › App Development; skip.dev › SkipFuse).
  The build plugin only warns when the import is missing,
  with "This file contains @Observables, but they will not be able to power your Android UI unless you 'import SkipFuse' or 'import SkipFuseUI'"
  (GitHub › skiptools/skipstone, `KotlinMessage.swift`); treat the warning as an error.

## Migrating from ObservableObject

- Move one screen at a time: the view model into the shared module with its dependencies,
  `ObservableObject` and `@Published` replaced by `@Observable`,
  Combine pipelines replaced by Swift Concurrency.
  Polymarket's first screen was Settings, running on both platforms a week later,
  and every migration shipped to iOS users in the normal release cycle (report).
- On iOS, `@StateObject` becomes `@State`, `@ObservedObject` becomes a plain property
  or `@Bindable` where the view needs bindings.
- Combine is not available to natively compiled Swift on Android;
  skip.dev's FAQ points to OpenCombine (skip.dev › FAQ).
  `ObservableObject`, `@Published` and a subset of publishers are documented
  for transpiled (Lite) modules only (skip.dev › SkipModel).

## Combine at the Kotlin boundary

Skip generates Kotlin APIs from Swift Concurrency, not from Combine publishers (Polymarket report),
so anything Kotlin calls gets an `async` function or a stream.
An adapter for code that still produces values through a callback:

```swift
// typecheck: shared
public final class PriceFeed: @unchecked Sendable {
    private var observers: [Int: (Int) -> Void] = [:]
    private var nextID = 0

    public init() {}

    @discardableResult
    public func observe(_ observer: @escaping (Int) -> Void) -> Int {
        nextID += 1
        observers[nextID] = observer
        return nextID
    }

    public func cancel(_ id: Int) {
        observers[id] = nil
    }

    public func publish(_ cents: Int) {
        for observer in observers.values { observer(cents) }
    }

    /// What Kotlin sees: a stream that stops observing when the collector goes away.
    public var updates: AsyncStream<Int> {
        AsyncStream { continuation in
            let id = observe { continuation.yield($0) }
            continuation.onTermination = { [weak self] _ in self?.cancel(id) }
        }
    }
}
```

`AsyncStream` bridges to a Kotlin `Flow`;
skip.dev's Bridging Reference ties that to the `kotlincompat` option
while the SkipBridge README states it without the condition (`bridge-surface.md`) —
check what your generated Kotlin exposes.
On iOS, older views that still want a publisher can get one from an `@Observable` property
through a small adapter in the iOS target; Polymarket wrote glue in both directions.

## Testing

Write the view model's tests with Swift Testing if the module is (or may become) a native Skip module:
`skip test` runs native test targets through Swift Testing only (skip.dev › Testing).
XCTest still runs with `swift test` on the host and with `skip android test` on a device or emulator.
