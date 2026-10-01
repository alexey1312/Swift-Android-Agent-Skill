// Does a plain NSObject subclass, with no @objc, build for Android?
import Foundation

public final class LegacyModel: NSObject {
    public let name: String

    public init(name: String) {
        self.name = name
        super.init()
    }

    public override var description: String {
        "LegacyModel(\(name))"
    }
}
