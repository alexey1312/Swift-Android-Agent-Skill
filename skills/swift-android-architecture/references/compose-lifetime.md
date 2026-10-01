# Lifetimes under Compose

On iOS a screen's view model is created just before the screen appears
and released when it is dismissed;
Swift reference counting makes `deinit` run at that moment.
On Android neither holds.

## What goes wrong

- **Compose keeps and reuses objects.**
  Polymarket's report calls this its hardest problem:
  "In ours it caused stale data, zombie websocket subscriptions, strange recomposition behavior and more bugs."
  (Swift Forums › Our Android app is written in Swift, @poly-rob, 2026-08-04, post 1).
- **The garbage collector decides when a Swift-backed object goes away.**
  "We still don't control when Android's garbage collector frees a Swift-backed object." (same post).
  A native Swift object that Kotlin holds is released only after Kotlin lets go of it,
  so its `deinit` runs late, or not before the process ends (*inference* from the report).
- **Caching view models across the graph makes it worse.**
  A `remember`ed map of view models at the navigation host keeps every screen's Swift object,
  and everything it subscribed to, alive for the life of the host.

## The rule

1. **One view model per navigation entry or presentation.**
   Polymarket built its own navigation stack, tab view, sheet and full-screen cover,
   plus a helper "that creates a fresh ViewModel for each new screen or presentation and tears its scope down on dismissal"
   (same post).
2. **Scope it to an Android owner that ends with the screen.**
   With Navigation Compose, `viewModel()` resolves to the current back-stack entry,
   and the instance "remains in memory as long as that destination is present in the back stack"
   (Android Developers › ViewModel Scoping APIs, updated 2026-04-30,
   <https://developer.android.com/topic/libraries/architecture/viewmodel/viewmodel-apis>).
   With Navigation 3, add the `rememberViewModelStoreNavEntryDecorator()` entry decorator
   from `androidx.lifecycle:lifecycle-viewmodel-navigation3`;
   an entry's view models are then created when it is added and cleared when it is removed
   (Android Developers › Navigation 3, updated 2026-09-22,
   <https://developer.android.com/guide/navigation/navigation-3/save-state>).
   A sheet needs its own store per presentation, cleared when it is dismissed.
3. **Stop the work explicitly.**
   Clearing a store only drops Kotlin's reference.
   Give the Swift view model a `close()` that cancels its tasks and subscriptions,
   and call it from the holder's `onCleared()`
   (or from `onDispose` of a `DisposableEffect` for composition-scoped state).
   This step is *inference*: the report says what they control is when a fresh view model is created,
   and the open-source example below clears stores without calling into Swift.
4. **Never cache view models in a map at the navigation host,**
   and give two instances of one class distinct keys under the same owner.

## Swift side

```swift
// typecheck: shared
import Foundation
import Observation

@MainActor
@Observable
public final class LedgerViewModel {
    public let accountID: String
    public private(set) var balanceCents = 0
    private var updates: Task<Void, Never>?

    public init(accountID: String) {
        self.accountID = accountID
    }

    /// Starts listening; call once when the screen appears.
    public func start(balances: AsyncStream<Int>) {
        guard updates == nil else { return }
        updates = Task { [weak self] in
            for await cents in balances {
                self?.balanceCents = cents
            }
        }
    }

    /// Stops everything the view model started. Android calls this when the
    /// back-stack entry or sheet that owns it goes away; iOS may call it on
    /// dismissal too, so neither platform depends on when `deinit` runs.
    public func close() {
        updates?.cancel()
        updates = nil
    }
}
```

## Kotlin side

A holder that ties the Swift object to an AndroidX `ViewModel`,
so the navigation entry's store decides its life and `onCleared()` closes it:

```kotlin
// typecheck: none — Kotlin; LedgerViewModel is the class Skip generates for the Swift type
class SwiftViewModelHolder<T : Any>(
    val model: T,
    private val close: (T) -> Unit,
) : ViewModel() {
    override fun onCleared() = close(model)
}

@Composable
fun LedgerRoute(accountID: String) {
    // Scoped to the current back-stack entry: a fresh instance per push, closed on pop.
    val holder = viewModel(key = "ledger-$accountID") {
        SwiftViewModelHolder(LedgerViewModel(accountID = accountID)) { it.close() }
    }
    LedgerScreen(holder.model)
}
```

The calls Kotlin can make on the generated class, and their names,
depend on the bridge (`bridge-surface.md`); check them in the exported library.

## An open-source example

theleftbit's BSWInterfaceKit (MIT) has the Compose side of this pattern,
from the forum thread's answer about lifetimes
(@pcifani, post 13: "very similar to what we do there"):
a holder that wraps a Swift view model in an AndroidX `ViewModel`,
a Navigation 3 display that gives each entry its own store and clears it on pop,
and a sheet that gives each presentation a fresh store.
It clears stores without calling into the Swift object,
and its default scope is the nearest owner, which can be the activity;
read it, then write your own — do not copy it.
Pinned:
<https://github.com/theleftbit/BSWInterfaceKit/tree/b74047a91f44875ad43cca7b778fc5b98d03b309/Sources/BSWInterfaceKit/Skip>.

## Verify

- An instrumented or emulator test that pushes, pops and re-pushes the screen
  and asserts the old instance was closed (a counter in a test double for the subscription source).
- The Swift side alone: `close()` cancels the task — a unit test that runs on the host and,
  in CI, on the emulator (`samples/SharedCore` in this skill's repository has one).
- Nothing here was measured on a device by this repository (`measured-behavior.md`).
