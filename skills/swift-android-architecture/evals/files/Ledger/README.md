# Ledger

Shared Swift core (`Shared/`, a Skip native module exported as an AAR)
under a native Kotlin and Compose app (`Android/`).
The iOS app uses the same `LedgerViewModel` from SwiftUI.

Bug report from QA (Android only):
after opening account A, going back, and opening account B a few times,
account A's screen briefly shows an old balance when reopened,
and the server log shows balance pushes still being delivered to listeners for screens that were closed long ago.
iOS behaves correctly.
