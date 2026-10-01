package com.example.ledger

import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import ledger.core.LedgerViewModel

@Composable
fun LedgerNavHost() {
    val nav = rememberNavController()
    // One view model per account, kept for the whole graph so going back is fast.
    val models = remember { mutableMapOf<String, LedgerViewModel>() }

    NavHost(navController = nav, startDestination = "accounts") {
        composable("accounts") {
            AccountList(onOpen = { id -> nav.navigate("ledger/$id") })
        }
        composable("ledger/{id}") { entry ->
            val id = entry.arguments?.getString("id") ?: return@composable
            val model = models.getOrPut(id) { LedgerViewModel(accountID = id) }
            LedgerScreen(model)
        }
    }
}

@Composable
fun LedgerScreen(model: LedgerViewModel) {
    Text("Balance: ${model.balanceCents / 100.0}")
}

@Composable
fun AccountList(onOpen: (String) -> Unit) {
    Text("Accounts")
}
