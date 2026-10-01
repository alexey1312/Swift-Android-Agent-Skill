import SharedCore
import XCTest

final class AsyncStreamAdapterTests: XCTestCase {
    func testStreamDeliversValuesInOrder() async {
        let broadcaster = Broadcaster<Int>()
        let stream = broadcaster.values()
        broadcaster.send(1)
        broadcaster.send(2)
        broadcaster.send(3)

        var received: [Int] = []
        for await value in stream {
            received.append(value)
            if received.count == 3 { break }
        }

        XCTAssertEqual(received, [1, 2, 3])
    }

    func testCancellingTheConsumerUnregistersTheObserver() async {
        let broadcaster = Broadcaster<Int>()
        let stream = broadcaster.values()
        XCTAssertEqual(broadcaster.observerCount, 1)

        let consumer = Task {
            for await _ in stream {}
        }
        consumer.cancel()
        await consumer.value

        XCTAssertEqual(broadcaster.observerCount, 0)
    }

    func testOnTerminationRunsWhenTheConsumingTaskIsCancelled() async {
        let unsubscribed = expectation(description: "unsubscribed")
        let stream = AsyncStream<Int>.observing { _ in
            { unsubscribed.fulfill() }
        }

        let consumer = Task {
            for await _ in stream {}
        }
        consumer.cancel()

        await fulfillment(of: [unsubscribed], timeout: 2)
        await consumer.value
    }
}
