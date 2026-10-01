// Does `import Combine` build for Android?
import Combine

public func makeCounter() -> CurrentValueSubject<Int, Never> {
    CurrentValueSubject(0)
}
