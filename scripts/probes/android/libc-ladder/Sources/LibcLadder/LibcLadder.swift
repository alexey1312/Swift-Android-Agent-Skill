// Does the C library import ladder build for Android?
#if canImport(Darwin)
import Darwin
#elseif canImport(Android)
import Android
#elseif canImport(Glibc)
import Glibc
#endif

public func hypotenuse(_ a: Double, _ b: Double) -> Double {
    sqrt(pow(a, 2) + pow(b, 2))
}
