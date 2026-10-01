package com.example.pricing

import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import pricing.kit.PriceBoard

// The rows never change after the first frame, even though PriceBoard.prices does on the Swift side.
@Composable
fun WatchlistScreen() {
    val board = remember { PriceBoard().also { it.connect() } }
    LazyColumn {
        items(board.prices.values.toList()) { price ->
            Text("${price.symbol}: ${price.cents / 100.0}")
        }
    }
}
