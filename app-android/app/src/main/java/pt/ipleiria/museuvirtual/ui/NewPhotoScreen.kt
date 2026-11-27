package pt.ipleiria.museuvirtual.ui

import android.content.Context
import android.content.Intent
import android.graphics.ImageDecoder
import android.net.Uri
import android.provider.OpenableColumns
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts.PickMultipleVisualMedia
import androidx.activity.result.contract.ActivityResultContracts.PickVisualMedia
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.GridItemSpan
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Check
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import pt.ipleiria.museuvirtual.data.PickedPhoto
import pt.ipleiria.museuvirtual.domain.PhotoRules

const val THUMB_MAX_PX = 400

/** Fator de amostragem (potência de 2) para o lado maior ficar <= maxPx sem carregar o original em memória. */
fun sampleSize(width: Int, height: Int, maxPx: Int): Int {
    var s = 1
    while (maxOf(width, height) / (s * 2) >= maxPx) s *= 2
    return s
}

/**
 * Imagem de um Uri reduzida (ImageDecoder aplica a rotação EXIF). Devolve também o tamanho original.
 * null se não abrir (ficheiro estragado ou permissão perdida).
 */
fun decodeUri(context: Context, uri: Uri, maxPx: Int): Triple<ImageBitmap, Int, Int>? = try {
    var w = 0
    var h = 0
    val bmp = ImageDecoder.decodeBitmap(ImageDecoder.createSource(context.contentResolver, uri)) { decoder, info, _ ->
        w = info.size.width
        h = info.size.height
        decoder.setTargetSampleSize(sampleSize(w, h, maxPx))
    }
    Triple(bmp.asImageBitmap(), w, h)
} catch (e: Exception) {
    null
}

/** Miniatura de um Uri (content:// ou ficheiro), carregada fora da thread da UI. */
@Composable
fun UriImage(uri: String, modifier: Modifier = Modifier, maxPx: Int = THUMB_MAX_PX, contentScale: ContentScale = ContentScale.Crop) {
    val context = LocalContext.current
    val img by produceState<ImageBitmap?>(null, uri) {
        value = withContext(Dispatchers.IO) { decodeUri(context, Uri.parse(uri), maxPx)?.first }
    }
    Box(modifier.background(MaterialTheme.colorScheme.surfaceVariant)) {
        img?.let { Image(it, contentDescription = null, Modifier.fillMaxSize(), contentScale = contentScale) }
    }
}

/** Uma fotografia escolhida: aceite (com tamanho) ou rejeitada (com o motivo). */
private class Picked(val uri: Uri, val thumb: ImageBitmap?, val width: Int, val height: Int, val problem: String?)

private fun inspect(context: Context, uri: Uri): Picked {
    val cr = context.contentResolver
    val size = cr.query(uri, arrayOf(OpenableColumns.SIZE), null, null, null)?.use {
        if (it.moveToFirst() && !it.isNull(0)) it.getLong(0) else -1L
    } ?: -1L
    PhotoRules.reject(cr.getType(uri), size)?.let { return Picked(uri, null, 0, 0, it) }
    val img = decodeUri(context, uri, THUMB_MAX_PX) ?: return Picked(uri, null, 0, 0, "não foi possível abrir")
    // O Photo Picker só dá leitura temporária: pedir permissão persistente para a miniatura continuar até ao upload.
    try { cr.takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION) } catch (_: SecurityException) {}
    return Picked(uri, img.first, img.second, img.third, null)
}

/** Nova fotografia (T043): escolher várias de uma vez, validar formato/tamanho e pré-visualizar antes de criar as fichas. */
@Composable
fun NewPhotoScreen(vm: PhotosViewModel, onCreated: (List<String>) -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var picked by remember { mutableStateOf<List<Picked>>(emptyList()) }
    var busy by remember { mutableStateOf(false) }

    val picker = rememberLauncherForActivityResult(PickMultipleVisualMedia(PhotoRules.MAX_PICK)) { uris ->
        if (uris.isEmpty()) return@rememberLauncherForActivityResult
        busy = true
        scope.launch {
            picked = withContext(Dispatchers.IO) { uris.map { inspect(context, it) } }
            busy = false
        }
    }
    val ok = picked.filter { it.problem == null }
    val bad = picked.filter { it.problem != null }

    LazyVerticalGrid(
        GridCells.Adaptive(104.dp),
        Modifier.fillMaxSize(),
        contentPadding = androidx.compose.foundation.layout.PaddingValues(16.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        item(span = { GridItemSpan(maxLineSpan) }) {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Nova fotografia", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.SemiBold)
                Text(
                    "Escolhe até ${PhotoRules.MAX_PICK} fotografias (JPEG, PNG, WebP ou HEIC, até 20 MB). " +
                        "A seguir preenches a ficha de cada uma.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                OutlinedButton(
                    onClick = { picker.launch(PickVisualMediaRequest(PickVisualMedia.ImageOnly)) },
                    enabled = !busy,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Icon(Icons.Filled.Add, contentDescription = null)
                    Spacer(Modifier.width(8.dp))
                    Text(if (picked.isEmpty()) "Escolher fotografias" else "Escolher outras")
                }
                when {
                    busy -> Box(Modifier.fillMaxWidth(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
                    picked.isEmpty() -> EmptyState("Nenhuma fotografia escolhida", "Sem permissões de galeria: o Android só dá acesso às que escolheres.")
                    else -> Text("${ok.size} prontas" + if (bad.isEmpty()) "" else " · ${bad.size} recusadas", style = MaterialTheme.typography.titleSmall)
                }
                bad.forEach {
                    Text("• ${it.uri.lastPathSegment}: ${it.problem}", color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
                }
            }
        }
        items(ok, key = { it.uri.toString() }) { p ->
            Box(Modifier.aspectRatio(1f).clip(RoundedCornerShape(8.dp)).background(MaterialTheme.colorScheme.surfaceVariant)) {
                p.thumb?.let { Image(it, contentDescription = null, Modifier.fillMaxSize(), contentScale = ContentScale.Crop) }
            }
        }
        if (ok.isNotEmpty()) item(span = { GridItemSpan(maxLineSpan) }) {
            Button(
                onClick = {
                    busy = true
                    vm.add(ok.map { PickedPhoto(it.uri.toString(), it.width, it.height) }) { ids ->
                        picked = emptyList()
                        busy = false
                        onCreated(ids)
                    }
                },
                enabled = !busy,
                modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
            ) {
                Icon(Icons.Filled.Check, contentDescription = null)
                Spacer(Modifier.width(8.dp))
                Text(if (ok.size == 1) "Criar ficha" else "Criar ${ok.size} fichas")
            }
        }
    }
}

/** Ecrã vazio comum: título e explicação, centrados. */
@Composable
fun EmptyState(title: String, text: String, modifier: Modifier = Modifier, action: (@Composable () -> Unit)? = null) {
    Column(
        modifier.fillMaxWidth().padding(vertical = 32.dp, horizontal = 16.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Text(title, style = MaterialTheme.typography.titleMedium)
        Text(text, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        action?.invoke()
    }
}
