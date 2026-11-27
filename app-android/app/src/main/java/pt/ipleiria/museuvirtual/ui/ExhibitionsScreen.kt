package pt.ipleiria.museuvirtual.ui

import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Share
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedCard
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import pt.ipleiria.museuvirtual.BuildConfig

/**
 * Abre o museu 3D do Unity em ecrã inteiro; "Voltar" no Unity fecha-o e regressa aqui (T014).
 * vr = true arranca já em modo RV para óculos tipo Cardboard (lido em VrMode.cs).
 * remoteToken: o do link do telemóvel-comando, para o link partilhado aqui servir sempre (RemotePad.cs).
 * collections: ids das coleções escolhidas (pastas em assets/colecoes), pela ordem em que o museu as monta.
 */
fun openMuseum3D(context: Context, collections: List<String>, vr: Boolean = false) {
    // Por nome: a app compila sem o módulo do Unity (ver settings.gradle.kts).
    context.startActivity(
        Intent().setClassName(context, "com.unity3d.player.UnityPlayerGameActivity")
            .putExtra("vr", vr)
            .putExtra("collections", collections.toTypedArray())
            .putExtra("remoteToken", RemoteLink.token(context))
    )
}

private const val LOCAL_NETWORK = "android.permission.ACCESS_LOCAL_NETWORK"  // Android 17 (API 37)

/** Envia só o link (WhatsApp, etc.), para abrir direto no outro telemóvel. */
fun shareRemoteLink(context: Context, url: String) {
    val send = Intent(Intent.ACTION_SEND).setType("text/plain").putExtra(Intent.EXTRA_TEXT, url)
    context.startActivity(Intent.createChooser(send, "Enviar link do comando"))
}

@Composable
fun ExhibitionsScreen() {
    val context = LocalContext.current
    // Android 17+: pedir "rede local" antes de abrir o museu/partilhar, senão o comando nunca liga.
    // O museu abre na mesma se a pessoa recusar (só o telemóvel-comando deixa de funcionar).
    var pending by remember { mutableStateOf<(() -> Unit)?>(null) }
    val askLocalNetwork = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) {
        pending?.invoke()
        pending = null
    }
    fun withLocalNetwork(action: () -> Unit) {
        if (Build.VERSION.SDK_INT < 37 ||
            ContextCompat.checkSelfPermission(context, LOCAL_NETWORK) == PackageManager.PERMISSION_GRANTED
        ) action() else {
            pending = action
            askLocalNetwork.launch(LOCAL_NETWORK)
        }
    }
    var link by remember { mutableStateOf(RemoteLink.url(context)) }
    var hotspot by remember { mutableStateOf(RemoteLink.isHotspotHost()) }
    val collections = remember { loadCollections(context.assets) }
    var chosen by rememberSaveable { mutableStateOf(ArrayList<String>()) }  // ArrayList: guarda-se no Bundle
    val selected = collections.map { it.id }.filter { it in chosen }
    val photoCount = collections.filter { it.id in chosen }.sumOf { it.photos.size }
    val canOpen = BuildConfig.HAS_UNITY && selected.isNotEmpty()
    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 16.dp, vertical = 20.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text("Museu 3D", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.SemiBold)
            Text(
                if (BuildConfig.HAS_UNITY) "Escolhe as coleções e entra no museu. Cada coleção é uma sala."
                else "Esta build não inclui o museu 3D (exportar do Unity: museum-unity/README.md).",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }

        // ---- coleções ----
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("Coleções", style = MaterialTheme.typography.titleMedium, modifier = Modifier.weight(1f))
            if (collections.isNotEmpty()) {
                val all = selected.size == collections.size
                TextButton(onClick = { chosen = if (all) ArrayList() else ArrayList(collections.map { it.id }) }) {
                    Text(if (all) "Limpar" else "Selecionar todas")
                }
            }
        }
        if (collections.isEmpty()) Text("Sem coleções na app.", color = MaterialTheme.colorScheme.error)
        collections.chunked(2).forEach { pair ->
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                pair.forEach { c ->
                    CollectionCard(c, checked = c.id in chosen, Modifier.weight(1f)) { on ->
                        chosen = ArrayList(if (on) chosen + c.id else chosen - c.id)
                    }
                }
                if (pair.size == 1) Spacer(Modifier.weight(1f))
            }
        }

        // ---- entrar ----
        Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer)) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text(
                    if (selected.isEmpty()) "Seleciona pelo menos uma coleção."
                    else "${selected.size} ${if (selected.size == 1) "sala" else "salas"} · $photoCount fotografias",
                    style = MaterialTheme.typography.titleSmall,
                    color = MaterialTheme.colorScheme.onPrimaryContainer,
                )
                Button(
                    onClick = { withLocalNetwork { openMuseum3D(context, selected) } },
                    enabled = canOpen,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Icon(Icons.Filled.PlayArrow, contentDescription = null)
                    Spacer(Modifier.width(8.dp))
                    Text("Visitar museu 3D")
                }
                OutlinedButton(
                    onClick = { withLocalNetwork { openMuseum3D(context, selected, vr = true) } },
                    enabled = canOpen,
                    modifier = Modifier.fillMaxWidth(),
                ) { Text("Visitar em RV (óculos Cardboard)") }
            }
        }

        // ---- comandos ----
        OutlinedCard {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Como andar no museu", style = MaterialTheme.typography.titleMedium)
                HelpLine("Ecrã", "dedo à esquerda anda, dedo à direita olha (os dois ao mesmo tempo). Toque curto num quadro abre-o.")
                HelpLine("RV", "olha à volta com a cabeça; toca no ecrã (ou A) para abrir o quadro para onde olhas.")
                HelpLine("Comando Xbox", "stick esquerdo anda, direito vira, A abre o quadro, B volta.")
            }
        }

        // ---- telemóvel como comando ----
        OutlinedCard {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text("Outro telemóvel como comando", style = MaterialTheme.typography.titleMedium)
                Text(
                    "Envia o link uma vez e abre-o no browser do outro telemóvel, na mesma rede Wi-Fi ou hotspot. " +
                        "O link é sempre o mesmo e liga-se sozinho quando entras no museu. " +
                        "Segura o telemóvel-comando na horizontal.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                if (hotspot) {
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Icon(Icons.Filled.Warning, contentDescription = null, tint = MaterialTheme.colorScheme.error)
                        Text(
                            "Este telemóvel está a fazer hotspot e assim o Android bloqueia o comando. Liga o hotspot no " +
                                "telemóvel-comando (ou usa um Wi-Fi), liga este telemóvel a essa rede e toca em Atualizar.",
                            color = MaterialTheme.colorScheme.error,
                            style = MaterialTheme.typography.bodyMedium,
                        )
                    }
                }
                Text(
                    link ?: "Sem Wi-Fi/hotspot: liga a rede e toca em Atualizar.",
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.Medium,
                )
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(
                        onClick = { link?.let { withLocalNetwork { shareRemoteLink(context, it) } } },
                        enabled = BuildConfig.HAS_UNITY && link != null,
                    ) {
                        Icon(Icons.Filled.Share, contentDescription = null)
                        Spacer(Modifier.width(8.dp))
                        Text("Partilhar link")
                    }
                    TextButton(onClick = { link = RemoteLink.url(context); hotspot = RemoteLink.isHotspotHost() }) {
                        Icon(Icons.Filled.Refresh, contentDescription = null)
                        Spacer(Modifier.width(6.dp))
                        Text("Atualizar")
                    }
                }
            }
        }
    }
}

@Composable
private fun HelpLine(label: String, text: String) {
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(label, style = MaterialTheme.typography.labelLarge, modifier = Modifier.width(96.dp))
        Text(text, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

/** Cartão da coleção: capa (1.ª fotografia), nome e n.º de fotografias; tocar marca/desmarca. */
@Composable
private fun CollectionCard(c: Collection, checked: Boolean, modifier: Modifier, onChange: (Boolean) -> Unit) {
    val assets = LocalContext.current.assets
    val thumb by produceState<ImageBitmap?>(null, c.id) {
        value = c.photos.firstOrNull()?.let { withContext(Dispatchers.IO) { loadThumbnail(assets, it, 400) } }
    }
    val colors = MaterialTheme.colorScheme
    OutlinedCard(
        modifier.toggleable(checked, role = Role.Checkbox, onValueChange = onChange),
        border = if (checked) BorderStroke(2.dp, colors.primary) else CardDefaults.outlinedCardBorder(),
    ) {
        Box(Modifier.fillMaxWidth().aspectRatio(4f / 3f).background(colors.surfaceVariant)) {
            thumb?.let { Image(it, contentDescription = null, Modifier.fillMaxSize(), contentScale = ContentScale.Crop) }
            if (checked) {
                Icon(
                    Icons.Filled.CheckCircle, contentDescription = "Selecionada", tint = colors.primary,
                    modifier = Modifier.align(Alignment.TopEnd).padding(8.dp).size(28.dp)
                        .background(colors.surface, CircleShape),
                )
            }
        }
        Column(Modifier.padding(horizontal = 12.dp, vertical = 10.dp)) {
            Text(c.title, style = MaterialTheme.typography.titleSmall, maxLines = 1, overflow = TextOverflow.Ellipsis)
            Text("${c.photos.size} fotografias", style = MaterialTheme.typography.bodySmall, color = colors.onSurfaceVariant)
        }
    }
}
