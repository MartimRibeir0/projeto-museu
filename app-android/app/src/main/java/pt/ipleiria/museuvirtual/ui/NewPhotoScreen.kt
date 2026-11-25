package pt.ipleiria.museuvirtual.ui

import android.graphics.ImageDecoder
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts.PickVisualMedia
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

const val PREVIEW_MAX_PX = 1600

/** Fator de amostragem (potência de 2) para o lado maior ficar <= maxPx sem carregar o original em memória. */
fun sampleSize(width: Int, height: Int, maxPx: Int): Int {
    var s = 1
    while (maxOf(width, height) / (s * 2) >= maxPx) s *= 2
    return s
}

@Composable
fun NewPhotoScreen() {
    val context = LocalContext.current
    var uri by rememberSaveable { mutableStateOf<Uri?>(null) }
    var bitmap by remember { mutableStateOf<ImageBitmap?>(null) }
    var error by remember { mutableStateOf<String?>(null) }

    // Photo Picker: sem permissão de galeria; o Uri só dá leitura temporária a esta app.
    val picker = rememberLauncherForActivityResult(PickVisualMedia()) { picked ->
        if (picked != null) uri = picked
    }

    LaunchedEffect(uri) {
        val u = uri ?: return@LaunchedEffect
        bitmap = null
        error = null
        try {
            bitmap = withContext(Dispatchers.IO) {
                val src = ImageDecoder.createSource(context.contentResolver, u)
                ImageDecoder.decodeBitmap(src) { decoder, info, _ ->
                    decoder.setTargetSampleSize(sampleSize(info.size.width, info.size.height, PREVIEW_MAX_PX))
                }.asImageBitmap()
            }
        } catch (e: Exception) {
            error = "Não foi possível abrir a imagem"
        }
    }

    Column(
        Modifier.fillMaxSize().padding(16.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Button(onClick = { picker.launch(PickVisualMediaRequest(PickVisualMedia.ImageOnly)) }) {
            Text("Escolher fotografia")
        }
        when {
            error != null -> Text(error!!, color = MaterialTheme.colorScheme.error)
            bitmap != null -> Image(
                bitmap!!,
                contentDescription = "Fotografia escolhida",
                modifier = Modifier.fillMaxWidth().weight(1f),
                contentScale = ContentScale.Fit,
            )
            uri != null -> CircularProgressIndicator()
            else -> Text("Nenhuma fotografia escolhida")
        }
    }
}
