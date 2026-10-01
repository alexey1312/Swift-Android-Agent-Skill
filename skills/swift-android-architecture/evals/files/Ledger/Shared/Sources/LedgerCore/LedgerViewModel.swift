import Foundation
import Observation
import SkipFuse

@Observable
public final class LedgerViewModel {
    public let accountID: String
    public private(set) var balanceCents = 0
    public private(set) var entries: [String] = []

    private var token: UUID?

    public init(accountID: String) {
        self.accountID = accountID
        token = BalanceSocket.shared.subscribe { [weak self] account, cents in
            guard let self, account == self.accountID else { return }
            self.balanceCents = cents
            self.entries.append("balance \(cents)")
        }
    }

    deinit {
        if let token { BalanceSocket.shared.unsubscribe(token) }
    }
}
