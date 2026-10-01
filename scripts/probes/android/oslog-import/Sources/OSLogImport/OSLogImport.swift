// Does `import OSLog` with a Logger build for Android?
import OSLog

public func logLaunch() {
    let logger = Logger(subsystem: "dev.example.probe", category: "probe")
    logger.info("launched")
}
