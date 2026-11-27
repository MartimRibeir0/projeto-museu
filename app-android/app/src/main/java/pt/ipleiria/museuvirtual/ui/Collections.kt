package pt.ipleiria.museuvirtual.ui

import android.content.res.AssetManager
import android.graphics.ImageDecoder
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap

const val COLLECTIONS_DIR = "colecoes"

/**
 * Coleção embutida na app: assets/colecoes/<id>/ com as fotografias (JPEG, lado maior <= 1280 px, já endireitadas;
 * pôr com app-android/tools/importar_colecao.py).
 * O Unity vai à mesma pasta (está no mesmo APK), por isso passa-se só o id.
 */
// shortcut: coleções fixas nos assets; passam a vir da API de exposições quando a app falar com o backend (T045).
data class Collection(val id: String, val photos: List<String>) {
    val title get() = collectionTitle(id)
}

/** "fotos_atoa_2" -> "Fotos atoa 2". */
fun collectionTitle(id: String) = id.replace('_', ' ').replaceFirstChar { it.uppercase() }

fun loadCollections(assets: AssetManager): List<Collection> =
    assets.list(COLLECTIONS_DIR).orEmpty().sorted().map { id ->
        Collection(id, assets.list("$COLLECTIONS_DIR/$id").orEmpty().sorted().map { "$COLLECTIONS_DIR/$id/$it" })
    }

/**
 * Miniatura de uma fotografia dos assets, reduzida sem carregar o original em memória.
 * ImageDecoder (e não BitmapFactory) porque aplica a rotação EXIF: fotografias verticais não aparecem deitadas.
 */
fun loadThumbnail(assets: AssetManager, path: String, maxPx: Int): ImageBitmap? = try {
    ImageDecoder.decodeBitmap(ImageDecoder.createSource(assets, path)) { decoder, info, _ ->
        decoder.setTargetSampleSize(sampleSize(info.size.width, info.size.height, maxPx))
    }.asImageBitmap()
} catch (e: java.io.IOException) {
    null  // imagem estragada: linha sem miniatura
}
