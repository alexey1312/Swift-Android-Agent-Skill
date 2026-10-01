// Does DispatchQueue.main.async build for Android?
// Whether the main queue is ever drained in an app is a runtime question this probe leaves open.
import Dispatch

public func runOnMain(_ work: @escaping @Sendable () -> Void) {
    DispatchQueue.main.async(execute: work)
}
