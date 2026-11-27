package pt.ipleiria.museuvirtual.domain

/** Categoria da fotografia. fromAi = sugerida pelo modelo (T044: distinguir da escolha humana). */
data class Label(val name: String, val fromAi: Boolean = false, val score: Float? = null, val confirmed: Boolean = !fromAi)

data class Photo(
    val id: String,
    val uri: String,  // ficheiro (API) ou content:// (escolhida no telemóvel, ainda sem upload)
    val width: Int,
    val height: Int,
    val title: String,
    val description: String,
    val memory: String,
    val labels: List<Label>,
    val exhibitionIds: List<String>,
) {
    val hasCard get() = title.isNotBlank()  // ficha preenchida (o título é obrigatório)
}

data class Exhibition(val id: String, val name: String, val description: String, val photoIds: List<String>)

/** Regras da ficha, iguais aos limites do backend (schemas.py). Devolve erro por campo; vazio = válida. */
object CardRules {
    const val TITLE_MAX = 200
    const val LABEL_MAX = 50
    const val LABELS_MAX = 10

    fun validate(title: String, labels: List<Label>): Map<String, String> = buildMap {
        when {
            title.isBlank() -> put("title", "O título é obrigatório.")
            title.length > TITLE_MAX -> put("title", "Máximo $TITLE_MAX caracteres.")
        }
        when {
            labels.size > LABELS_MAX -> put("labels", "Máximo $LABELS_MAX categorias.")
            labels.any { it.name.isBlank() || it.name.length > LABEL_MAX } -> put("labels", "Cada categoria tem 1 a $LABEL_MAX caracteres.")
            labels.any { it.fromAi && !it.confirmed } -> put("labels", "Confirma ou remove as sugestões da IA.")
        }
    }
}

/** Ficheiros aceites no upload (mesma regra que o museu 3D: > 20 MB não se abre no telemóvel). */
object PhotoRules {
    const val MAX_BYTES = 20L shl 20
    const val MAX_PICK = 20
    val MIME = setOf("image/jpeg", "image/png", "image/webp", "image/heic", "image/heif")

    /** null = aceite; senão, o motivo. size < 0 = desconhecido (deixa passar: o servidor volta a validar). */
    fun reject(mime: String?, size: Long): String? = when {
        mime == null || mime !in MIME -> "formato não suportado (${mime ?: "desconhecido"})"
        size > MAX_BYTES -> "maior que 20 MB"
        else -> null
    }
}
