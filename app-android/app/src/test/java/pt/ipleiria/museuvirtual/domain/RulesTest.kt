package pt.ipleiria.museuvirtual.domain

import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import pt.ipleiria.museuvirtual.data.FakePhotoRepository
import pt.ipleiria.museuvirtual.data.LabelDto
import pt.ipleiria.museuvirtual.data.PickedPhoto
import pt.ipleiria.museuvirtual.data.toDomain

class RulesTest {
    @Test
    fun fichaPedeTituloELimites() {
        assertEquals(setOf("title"), CardRules.validate("  ", emptyList()).keys)
        assertEquals(setOf("title"), CardRules.validate("x".repeat(201), emptyList()).keys)
        assertTrue(CardRules.validate("Praia", listOf(Label("Mar"))).isEmpty())
        assertEquals(setOf("labels"), CardRules.validate("Praia", List(11) { Label("c$it") }).keys)
    }

    @Test
    fun sugestaoDaIaTemDeSerConfirmada() {
        val ai = LabelDto("Paisagem", 0.9f, source = "ai").toDomain()
        assertEquals(setOf("labels"), CardRules.validate("Praia", listOf(ai)).keys)
        assertTrue(CardRules.validate("Praia", listOf(ai.copy(confirmed = true))).isEmpty())
        assertTrue(LabelDto("Mar").toDomain().confirmed)  // escolha humana já conta como confirmada
    }

    @Test
    fun ficheirosAceites() {
        assertNull(PhotoRules.reject("image/jpeg", 5_000_000))
        assertNull(PhotoRules.reject("image/heic", -1))
        assertEquals("maior que 20 MB", PhotoRules.reject("image/png", 21L shl 20))
        assertTrue(PhotoRules.reject("video/mp4", 1)!!.startsWith("formato"))
        assertTrue(PhotoRules.reject(null, 1)!!.startsWith("formato"))
    }

    @Test
    fun guardarFichaAtualizaExposicoes() = runBlocking {
        val repo = FakePhotoRepository()
        val (a, b) = repo.add(listOf(PickedPhoto("content://a", 4, 3), PickedPhoto("content://b", 3, 4)))
        repo.saveCard(a, " Praia ", "", "", listOf(Label("Mar")), listOf("ex-ferias"))
        assertEquals("Praia", repo.photos.value.first { it.id == a }.title)
        assertEquals(listOf(a), repo.exhibitions.value.first { it.id == "ex-ferias" }.photoIds)
        repo.saveCard(a, "Praia", "", "", emptyList(), listOf("ex-familia"))
        assertEquals(emptyList<String>(), repo.exhibitions.value.first { it.id == "ex-ferias" }.photoIds)
        repo.delete(a)
        assertEquals(listOf(b), repo.photos.value.map { it.id })
        assertEquals(emptyList<String>(), repo.exhibitions.value.first { it.id == "ex-familia" }.photoIds)
    }
}
