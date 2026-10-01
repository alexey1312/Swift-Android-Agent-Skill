// Do @objc and #selector build for Android?
import Foundation

public final class Button: NSObject {
    @objc public func tapped() {}
}

public func tapSelector() -> Selector {
    #selector(Button.tapped)
}
