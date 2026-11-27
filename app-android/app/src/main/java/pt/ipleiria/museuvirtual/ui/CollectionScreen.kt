package pt.ipleiria.museuvirtual.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.GridItemSpan
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedCard
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import pt.ipleiria.museuvirtual.domain.Photo

/** Coleção pessoal (T042): grelha de fichas, com estados a carregar / erro / vazio. */
@Composable
fun CollectionScreen(vm: PhotosViewModel, onOpen: (String) -> Unit, onAdd: () -> Unit) {
    val state by vm.collection.collectAsStateWithLifecycle()
    when (val s = state) {
        UiState.Loading -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
        is UiState.Error -> EmptyState("Não foi possível carregar", s.message, Modifier.fillMaxSize())
        UiState.Empty -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            EmptyState("A tua coleção está vazia", "Junta fotografias e conta a história de cada uma.") {
                Button(onClick = onAdd) { Text("Adicionar fotografias") }
            }
        }
        is UiState.Content -> {
            val pending = s.data.count { !it.hasCard }
            LazyVerticalGrid(
                GridCells.Adaptive(150.dp),
                Modifier.fillMaxSize(),
                contentPadding = PaddingValues(16.dp),
                horizontalArrangement = Arrangement.spacedBy(12.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                item(span = { GridItemSpan(maxLineSpan) }) {
                    Column {
                        Text("Coleção", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.SemiBold)
                        Text(
                            "${s.data.size} fotografias" + if (pending > 0) " · $pending sem ficha" else "",
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
                items(s.data, key = { it.id }) { PhotoCard(it) { onOpen(it.id) } }
            }
        }
    }
}

@Composable
private fun PhotoCard(p: Photo, onClick: () -> Unit) {
    OutlinedCard(Modifier.fillMaxWidth().clickable(onClick = onClick)) {
        UriImage(p.uri, Modifier.fillMaxWidth().aspectRatio(1f))
        Column(Modifier.padding(horizontal = 12.dp, vertical = 10.dp)) {
            if (p.hasCard) {
                Text(p.title, style = MaterialTheme.typography.titleSmall, maxLines = 1, overflow = TextOverflow.Ellipsis)
                Text(
                    p.labels.joinToString(" · ") { it.name }.ifEmpty { "Sem categorias" },
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            } else {
                Text("Sem ficha", style = MaterialTheme.typography.titleSmall, color = MaterialTheme.colorScheme.error)
                Text("Toca para preencher", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
}
