package pt.ipleiria.museuvirtual.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.consumeWindowInsets
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.InputChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import pt.ipleiria.museuvirtual.domain.CardRules
import pt.ipleiria.museuvirtual.domain.Label

// shortcut: lista fixa até haver o modelo de classificação (T017/T050); depois vêm do /predict com fromAi = true.
private val SUGGESTED = listOf("Paisagem", "Pessoas", "Animais", "Comida", "Cidade", "Natureza", "Família", "Viagem")

/** Ficha da fotografia (T044): título, descrição, memória, categorias e exposições, com validação. */
@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
fun EditPhotoScreen(vm: PhotosViewModel, id: String, onBack: () -> Unit, onDone: (next: String?) -> Unit) {
    val photos by vm.photos.collectAsStateWithLifecycle()
    val exhibitions by vm.exhibitions.collectAsStateWithLifecycle()
    val photo = photos.firstOrNull { it.id == id }
    if (photo == null) {  // apagada entretanto ou id errado
        EmptyState("Fotografia não encontrada", "Pode ter sido apagada.", Modifier.fillMaxSize()) { Button(onClick = onBack) { Text("Voltar") } }
        return
    }

    var title by rememberSaveable(id) { mutableStateOf(photo.title) }
    var description by rememberSaveable(id) { mutableStateOf(photo.description) }
    var memory by rememberSaveable(id) { mutableStateOf(photo.memory) }
    var newLabel by rememberSaveable(id) { mutableStateOf("") }
    val labels = remember(id) { mutableStateListOf(*photo.labels.toTypedArray()) }
    val chosenEx = remember(id) { mutableStateListOf(*photo.exhibitionIds.toTypedArray()) }
    var errors by remember(id) { mutableStateOf(emptyMap<String, String>()) }
    var confirmDelete by remember { mutableStateOf(false) }

    fun addLabel(name: String) {
        val n = name.trim()
        if (n.isNotEmpty() && labels.none { it.name.equals(n, ignoreCase = true) }) labels += Label(n)
        newLabel = ""
    }

    // Insets a zero: a barra de estado e a de navegação já vêm tratadas pelo Scaffold de MuseuApp.
    Scaffold(
        contentWindowInsets = WindowInsets(0),
        topBar = {
            TopAppBar(
                windowInsets = WindowInsets(0),
                title = { Text(if (photo.hasCard) "Editar ficha" else "Nova ficha") },
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Voltar") } },
                actions = { IconButton(onClick = { confirmDelete = true }) { Icon(Icons.Filled.Delete, "Apagar fotografia") } },
            )
        },
    ) { padding ->
        Column(
            Modifier.fillMaxSize().padding(padding).consumeWindowInsets(padding).imePadding().verticalScroll(rememberScrollState()).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            UriImage(
                photo.uri,
                Modifier.fillMaxWidth().height(240.dp).clip(RoundedCornerShape(12.dp)),
                maxPx = 1200, contentScale = ContentScale.Fit,
            )
            OutlinedTextField(
                title, { title = it }, Modifier.fillMaxWidth(),
                label = { Text("Título *") }, singleLine = true,
                isError = "title" in errors,
                supportingText = { Text(errors["title"] ?: "${title.length}/${CardRules.TITLE_MAX}") },
            )
            OutlinedTextField(description, { description = it }, Modifier.fillMaxWidth(), label = { Text("Descrição") }, minLines = 2)
            OutlinedTextField(
                memory, { memory = it }, Modifier.fillMaxWidth(),
                label = { Text("Memória") }, placeholder = { Text("O que aconteceu neste dia?") }, minLines = 3,
            )

            Text("Categorias", style = MaterialTheme.typography.titleMedium)
            if (labels.isNotEmpty()) FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                labels.forEachIndexed { i, l ->
                    InputChip(
                        selected = l.confirmed,
                        onClick = { if (l.fromAi) labels[i] = l.copy(confirmed = !l.confirmed) },
                        label = { Text(if (l.fromAi) "${l.name} · IA ${((l.score ?: 0f) * 100).toInt()}%" else l.name) },
                        leadingIcon = if (l.fromAi && l.confirmed) ({ Icon(Icons.Filled.Check, null, Modifier.size(18.dp)) }) else null,
                        trailingIcon = {
                            IconButton(onClick = { labels.removeAt(i) }, Modifier.size(24.dp)) {
                                Icon(Icons.Filled.Close, "Remover ${l.name}", Modifier.size(16.dp))
                            }
                        },
                    )
                }
            }
            Row(verticalAlignment = Alignment.CenterVertically) {
                OutlinedTextField(
                    newLabel, { newLabel = it.take(CardRules.LABEL_MAX) }, Modifier.weight(1f),
                    label = { Text("Nova categoria") }, singleLine = true,
                    keyboardOptions = KeyboardOptions(imeAction = ImeAction.Done),
                    keyboardActions = KeyboardActions(onDone = { addLabel(newLabel) }),
                )
                IconButton(onClick = { addLabel(newLabel) }, enabled = newLabel.isNotBlank()) { Icon(Icons.Filled.Add, "Adicionar categoria") }
            }
            val suggestions = SUGGESTED.filter { s -> labels.none { it.name.equals(s, ignoreCase = true) } }
            if (suggestions.isNotEmpty()) FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                suggestions.forEach { s -> AssistChip(onClick = { addLabel(s) }, label = { Text(s) }, leadingIcon = { Icon(Icons.Filled.Add, null, Modifier.size(16.dp)) }) }
            }
            errors["labels"]?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) }

            Text("Exposições", style = MaterialTheme.typography.titleMedium)
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                exhibitions.forEach { e ->
                    val on = e.id in chosenEx
                    FilterChip(
                        selected = on,
                        onClick = { if (on) chosenEx -= e.id else chosenEx += e.id },
                        label = { Text(e.name) },
                        leadingIcon = if (on) ({ Icon(Icons.Filled.Check, null, Modifier.size(18.dp)) }) else null,
                    )
                }
            }

            Box(Modifier.fillMaxWidth().padding(top = 8.dp)) {
                Button(
                    onClick = {
                        errors = CardRules.validate(title, labels)
                        if (errors.isEmpty()) vm.save(id, title, description, memory, labels.toList(), chosenEx.toList(), onDone)
                    },
                    modifier = Modifier.fillMaxWidth(),
                ) { Text("Guardar ficha") }
            }
        }
    }

    if (confirmDelete) AlertDialog(
        onDismissRequest = { confirmDelete = false },
        title = { Text("Apagar fotografia?") },
        text = { Text("Sai da coleção e das exposições. A fotografia original no telemóvel não é apagada.") },
        confirmButton = { TextButton(onClick = { confirmDelete = false; vm.delete(id, onBack) }) { Text("Apagar") } },
        dismissButton = { TextButton(onClick = { confirmDelete = false }) { Text("Cancelar") } },
    )
}
