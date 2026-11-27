package pt.ipleiria.museuvirtual.data

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import pt.ipleiria.museuvirtual.domain.Exhibition
import pt.ipleiria.museuvirtual.domain.Label
import pt.ipleiria.museuvirtual.domain.Photo
import java.util.UUID

/** Fonte das fotografias e exposições. A UI só conhece isto: trocar o fake pela API (T046) não mexe nos ecrãs. */
interface PhotoRepository {
    val photos: StateFlow<List<Photo>>
    val exhibitions: StateFlow<List<Exhibition>>

    /** Fotografias escolhidas no telemóvel, ainda sem ficha. Devolve os ids novos. */
    suspend fun add(picked: List<PickedPhoto>): List<String>

    suspend fun saveCard(id: String, title: String, description: String, memory: String, labels: List<Label>, exhibitionIds: List<String>)

    suspend fun delete(id: String)
}

data class PickedPhoto(val uri: String, val width: Int, val height: Int)

// shortcut: tudo em memória (perde-se ao fechar a app); passa a API + cache (T046/T047) quando o backend estiver ligado.
class FakePhotoRepository : PhotoRepository {
    private val _photos = MutableStateFlow<List<Photo>>(emptyList())
    private val _exhibitions = MutableStateFlow(
        listOf(
            Exhibition("ex-ferias", "Férias", "Viagens e passeios", emptyList()),
            Exhibition("ex-familia", "Família", "Momentos em família", emptyList()),
        )
    )
    override val photos = _photos.asStateFlow()
    override val exhibitions = _exhibitions.asStateFlow()

    override suspend fun add(picked: List<PickedPhoto>): List<String> {
        val new = picked.map { Photo(UUID.randomUUID().toString(), it.uri, it.width, it.height, "", "", "", emptyList(), emptyList()) }
        _photos.update { new + it }
        return new.map { it.id }
    }

    override suspend fun saveCard(
        id: String, title: String, description: String, memory: String, labels: List<Label>, exhibitionIds: List<String>,
    ) {
        _photos.update { list ->
            list.map { if (it.id == id) it.copy(title = title.trim(), description = description.trim(), memory = memory.trim(), labels = labels, exhibitionIds = exhibitionIds) else it }
        }
        _exhibitions.update { list ->
            list.map { e ->
                val has = id in e.photoIds
                when {
                    e.id in exhibitionIds && !has -> e.copy(photoIds = e.photoIds + id)
                    e.id !in exhibitionIds && has -> e.copy(photoIds = e.photoIds - id)
                    else -> e
                }
            }
        }
    }

    override suspend fun delete(id: String) {
        _photos.update { list -> list.filterNot { it.id == id } }
        _exhibitions.update { list -> list.map { it.copy(photoIds = it.photoIds - id) } }
    }
}
