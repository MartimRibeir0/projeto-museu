package pt.ipleiria.museuvirtual.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import pt.ipleiria.museuvirtual.data.FakePhotoRepository
import pt.ipleiria.museuvirtual.data.PhotoRepository
import pt.ipleiria.museuvirtual.data.PickedPhoto
import pt.ipleiria.museuvirtual.domain.Label
import pt.ipleiria.museuvirtual.domain.Photo

/** Estado de um ecrã que carrega dados: a carregar, erro, vazio ou com conteúdo (T042). */
sealed interface UiState<out T> {
    data object Loading : UiState<Nothing>
    data class Error(val message: String) : UiState<Nothing>
    data object Empty : UiState<Nothing>
    data class Content<T>(val data: T) : UiState<T>
}

/** Dependências da app num só sítio; trocar FakePhotoRepository pela API muda só esta linha (T045/T046). */
object AppGraph {
    val photos: PhotoRepository by lazy { FakePhotoRepository() }
}

/** Estado da sessão partilhado pelos ecrãs (criado uma vez em MuseuApp, não por destino). */
class PhotosViewModel(private val repo: PhotoRepository) : ViewModel() {
    val collection: StateFlow<UiState<List<Photo>>> = repo.photos
        .map { if (it.isEmpty()) UiState.Empty else UiState.Content(it) }
        .catch { emit(UiState.Error(it.message ?: "Erro ao carregar a coleção")) }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), UiState.Loading)

    val photos = repo.photos
    val exhibitions = repo.exhibitions

    fun add(picked: List<PickedPhoto>, then: (List<String>) -> Unit) = viewModelScope.launch { then(repo.add(picked)) }

    /** Grava a ficha e devolve (em then) a próxima fotografia ainda sem ficha, para preencher em sequência. */
    fun save(id: String, title: String, description: String, memory: String, labels: List<Label>, exhibitionIds: List<String>, then: (String?) -> Unit) =
        viewModelScope.launch {
            repo.saveCard(id, title, description, memory, labels, exhibitionIds)
            then(repo.photos.value.firstOrNull { !it.hasCard && it.id != id }?.id)
        }

    fun delete(id: String, then: () -> Unit) = viewModelScope.launch { repo.delete(id); then() }
}
