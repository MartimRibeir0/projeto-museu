# app-android

App Kotlin/Jetpack Compose (DDM).

## Versões

AGP 9.4 (Kotlin 2.4.21 embutido) · Gradle 9.6 · Compose BOM 2025.08.01 · Material 3 · compileSdk/targetSdk 37 · minSdk 28 (Android 9, por causa do `ImageDecoder`).

## Abrir e compilar

Abrir a pasta `app-android/` no Android Studio (cria o `local.properties` com o caminho do SDK). Na linha de comandos:

```sh
# Windows (Git Bash): usar o JDK do Android Studio
export JAVA_HOME="/c/Program Files/Android/Android Studio/jbr"
./gradlew assembleDebug testDebugUnitTest
```
APK: `app/build/outputs/apk/debug/app-debug.apk`.

## O que existe

- Navegação inferior: Coleção, Nova fotografia, Exposições. Cada separador mantém o seu estado.
- Nova fotografia: Photo Picker (`PickVisualMedia`), sem permissão de acesso à galeria. A imagem é reduzida ao abrir (lado maior ≤ 1600 px) para não carregar o original inteiro em memória.

## Limites do Uri do Photo Picker

O Uri dá leitura **temporária** só a esta app: não se pode guardar para mais tarde nem passar ao Unity. Para enviar à API, ler o conteúdo logo a seguir à escolha (ou copiar para `cacheDir`) e fazer upload desse ficheiro.
