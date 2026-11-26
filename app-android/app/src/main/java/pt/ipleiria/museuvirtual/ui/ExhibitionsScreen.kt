package pt.ipleiria.museuvirtual.ui

import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import pt.ipleiria.museuvirtual.BuildConfig

/**
 * Abre o museu 3D do Unity em ecrã inteiro; "Voltar" no Unity fecha-o e regressa aqui (T014).
 * vr = true arranca já em modo RV para óculos tipo Cardboard (lido em VrMode.cs).
 * remoteToken: o do link do telemóvel-comando, para o link partilhado aqui servir sempre (RemotePad.cs).
 */
fun openMuseum3D(context: Context, vr: Boolean = false) {
    // Por nome: a app compila sem o módulo do Unity (ver settings.gradle.kts).
    context.startActivity(
        Intent().setClassName(context, "com.unity3d.player.UnityPlayerGameActivity")
            .putExtra("vr", vr)
            .putExtra("remoteToken", RemoteLink.token(context))
    )
}

private const val LOCAL_NETWORK = "android.permission.ACCESS_LOCAL_NETWORK"  // Android 17 (API 37)

/** Envia só o link (WhatsApp, etc.), para abrir direto no outro telemóvel. */
fun shareRemoteLink(context: Context, url: String) {
    val send = Intent(Intent.ACTION_SEND).setType("text/plain").putExtra(Intent.EXTRA_TEXT, url)
    context.startActivity(Intent.createChooser(send, "Enviar link do comando"))
}

// shortcut: só o museu 3D; a lista de exposições vem com a API (T045).
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
    Column(
        Modifier.fillMaxSize().padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp, Alignment.CenterVertically),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text("Museu 3D", style = MaterialTheme.typography.headlineSmall)
        Text(
            if (BuildConfig.HAS_UNITY) "Percorre o museu e a sala do gémeo digital."
            else "Esta build não inclui o museu 3D (exportar do Unity: museum-unity/README.md).",
            style = MaterialTheme.typography.bodyMedium,
        )
        Button(onClick = { withLocalNetwork { openMuseum3D(context) } }, enabled = BuildConfig.HAS_UNITY) {
            Text("Visitar museu 3D")
        }
        OutlinedButton(onClick = { withLocalNetwork { openMuseum3D(context, vr = true) } }, enabled = BuildConfig.HAS_UNITY) {
            Text("Visitar em RV (óculos)")
        }

        HorizontalDivider(Modifier.padding(vertical = 8.dp))
        Text("Outro telemóvel como comando", style = MaterialTheme.typography.titleMedium)
        Text(
            "Envia o link uma vez e abre-o no browser do outro telemóvel, na mesma rede Wi-Fi ou hotspot. " +
                "O link é sempre o mesmo e liga-se sozinho quando entras no museu. " +
                "Segura o telemóvel-comando na horizontal.",
            style = MaterialTheme.typography.bodySmall,
            textAlign = TextAlign.Center,
        )
        if (hotspot) {
            Text(
                "Este telemóvel está a fazer hotspot e assim o Android bloqueia o comando. Liga o hotspot no " +
                    "telemóvel-comando (ou usa um Wi-Fi), liga este telemóvel a essa rede e toca em Atualizar.",
                color = MaterialTheme.colorScheme.error,
                style = MaterialTheme.typography.bodyMedium,
                textAlign = TextAlign.Center,
            )
        }
        Text(link ?: "Sem Wi-Fi/hotspot: liga a rede e toca em Atualizar.", style = MaterialTheme.typography.bodyMedium)
        Button(onClick = { link?.let { withLocalNetwork { shareRemoteLink(context, it) } } }, enabled = BuildConfig.HAS_UNITY && link != null) {
            Text("Partilhar link do comando")
        }
        TextButton(onClick = { link = RemoteLink.url(context); hotspot = RemoteLink.isHotspotHost() }) { Text("Atualizar") }

        Text(
            "Comando Xbox (Bluetooth) também serve: stick esquerdo anda, direito vira, A abre o quadro, B volta.",
            style = MaterialTheme.typography.bodySmall,
            textAlign = TextAlign.Center,
        )
    }
}
