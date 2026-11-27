package pt.ipleiria.museuvirtual.data

import pt.ipleiria.museuvirtual.domain.Exhibition
import pt.ipleiria.museuvirtual.domain.Label
import pt.ipleiria.museuvirtual.domain.Photo

/*
 * DTOs com os mesmos campos (camelCase) que o backend devolve: backend/app/schemas.py.
 * Datas em ISO 8601 UTC (texto), ids UUID (texto). Quando houver cliente HTTP (T046) só muda o Repository.
 */

data class LabelDto(
    val name: String,
    val score: Float? = null,
    val source: String = "human",  // "ai" | "human"
    val modelVersion: String? = null,
    val confirmed: Boolean = false,
)

data class PhotoDto(
    val id: String,
    val title: String?,
    val description: String?,
    val memory: String?,
    val takenAt: String?,
    val location: String?,
    val width: Int,
    val height: Int,
    val mimeType: String,
    val fileUrl: String,
    val thumbnailUrl: String,
    val labels: List<LabelDto>,
    val exhibitionIds: List<String>,
    val version: Int,
    val createdAt: String,
    val updatedAt: String,
)

/** Corpo do PATCH /photos/{id}: só os campos não nulos mudam. */
data class PhotoUpdateDto(
    val title: String? = null,
    val description: String? = null,
    val memory: String? = null,
    val labels: List<LabelDto>? = null,
)

data class ExhibitionPhotoDto(val photoId: String, val position: Int)

data class ExhibitionDto(
    val id: String,
    val name: String,
    val description: String?,
    val photos: List<ExhibitionPhotoDto>,
    val createdAt: String,
    val updatedAt: String,
)

data class DeviceDto(
    val id: String,
    val kind: String,
    val name: String,
    val online: Boolean,
    val lastSeen: String?,
    val observedState: Map<String, Any?>?,
)

data class PredictionDto(val labels: List<LabelDto>, val modelVersion: String)

// ---- DTO <-> domínio ----

fun LabelDto.toDomain() = Label(name, fromAi = source == "ai", score = score, confirmed = confirmed || source == "human")
fun Label.toDto() = LabelDto(name, score, if (fromAi) "ai" else "human", confirmed = confirmed)

fun PhotoDto.toDomain() = Photo(
    id, fileUrl, width, height, title.orEmpty(), description.orEmpty(), memory.orEmpty(),
    labels.map { it.toDomain() }, exhibitionIds,
)

fun ExhibitionDto.toDomain() = Exhibition(id, name, description.orEmpty(), photos.sortedBy { it.position }.map { it.photoId })
