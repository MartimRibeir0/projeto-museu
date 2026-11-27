package pt.ipleiria.museuvirtual.ui

import org.junit.Assert.assertEquals
import org.junit.Test

class CollectionsTest {
    @Test
    fun tituloDaPasta() {
        assertEquals("Fotos atoa", collectionTitle("fotos_atoa"))
        assertEquals("Fotos atoa 2", collectionTitle("fotos_atoa_2"))
    }
}
