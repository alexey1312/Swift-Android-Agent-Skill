import PassKit
import SwiftUI
import TripNotesKit

struct AddToWalletButton: View {
    let trip: Trip

    var body: some View {
        Button("Add to Wallet") {
            guard PKAddPassesViewController.canAddPasses() else { return }
            // Fetches the signed .pkpass for this trip and presents PKAddPassesViewController.
        }
    }
}
