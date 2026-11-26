# museum-unity

Projeto Unity do museu 3D/RV/RA (RVA). **Unity 6000.0.85f2 (6 LTS)**, Built-in Render Pipeline, Input Manager antigo.

## Refazer a partir do Blender

Os prefabs e a cena são gerados a partir de `blender/export/` (ver `blender/README.md`). Depois de mudar o Blender:

- no Editor: menu **Museu → 1. Importar do Blender** e **Museu → 2. Criar prefabs e cena**;
- ou sem abrir o Editor (fechá-lo antes):
  `"C:\Program Files\Unity\Hub\Editor\6000.0.85f2\Editor\Unity.exe" -batchmode -quit -projectPath museum-unity -executeMethod MuseumSetup.RunAll -logFile -`

O setup falha se o visitante não ficar no chão ou atravessar uma parede, e grava `docs/unity/entrada.png` e `docs/unity/gemeo.png`. **Não editar à mão** `Assets/Prefabs/*` nem `Assets/Scenes/Museum.unity`: são refeitos em cada execução.

## O que há

| Caminho | O que é |
|---------|---------|
| `Assets/Models/Museum/` | Cópia dos FBX e texturas do Blender. Import com "Bake Axis Conversion", UV2 para lightmaps e hierarquia preservada (`Editor/MuseumModelPostprocessor.cs`) |
| `Assets/Prefabs/MuseumShell` | Entrada + sala do gémeo digital, com colliders |
| `Assets/Prefabs/CorridorModule` | Módulo de corredor de 4 m com 2 slots (`*_Slot_L/R`) vazios |
| `Assets/Prefabs/Frame_{Landscape,Portrait,Square}` | Moldura com `BoxCollider` (para o toque) e fotografia no filho `Photo_*` |
| `Assets/Scenes/Museum.unity` | Casca + 3 módulos + molduras nos slots; luz cozinhada; `Player` |
| `Assets/Scripts/BlenderProps.cs` | `deviceId`/`aspect`/`slot` vindos do Blender |
| `Assets/Scripts/FirstPersonTouch.cs` | Navegação: metade esquerda do ecrã anda, metade direita olha; WASD + botão direito no Editor |

Luz: 1 ponto por divisão, cozinhado (lightmap 8 texels/m, 1 mapa 1024). `Twin_Light/Twin_Light_Source` fica em tempo real para acompanhar o estado do candeeiro do gémeo.

## APK de teste

Menu **Museu → 3. Build APK de teste**, ou `-executeMethod MuseumBuild.Apk` (com `-buildTarget Android`). Sai em `Builds/museu3d.apk` (IL2CPP, ARM64 para telemóveis + x86_64 para o emulador do Android Studio). Instalar: `adb install -r Builds/museu3d.apk`.

## Dentro da app Android (Unity as a Library, T014)

1. Menu **Museu → 4. Exportar para a app Android** (ou `-executeMethod MuseumBuild.Export` com `-buildTarget Android`): gera `Builds/android-export`. Refazer sempre que o museu mudar.
2. Compilar `app-android` normalmente: o `settings.gradle.kts` inclui `unityLibrary` dessa pasta se existir. O 1.º build demora (compila IL2CPP em C++).
3. Na app: separador **Exposições → Visitar museu 3D**. O Unity corre no processo `:unity`; "Voltar" (`Assets/Scripts/BackToApp.cs`) ou recuar do Android fecham-no e voltam à app.

## RV (Cardboard) e comandos

- **Modo RV:** botão "Modo RV", Menu no comando, ou abrir pela app em "Visitar em RV (óculos)". Ecrã dividido + giroscópio (`VrMode.cs`). Recuar/B sai do RV.
- **Comando Xbox** (Bluetooth): stick esq. anda, dir. olha (em RV vira 30°), A abre quadro, B fecha/volta, Menu liga RV, Ver recentra (`Pad.cs`).
- **Outro telemóvel como comando:** botão "Comando telemóvel" → enviar o link (mesma rede Wi-Fi) → abrir no browser do outro telemóvel, **na horizontal**. Servidor na porta 47615 com token no link (`RemotePad.cs`, `RemoteServer.cs`, página `Assets/Resources/remote.html`). Verificar o servidor sem telemóvel: `-executeMethod RemoteServerCheck.Run`.
- Redes de convidados/escolas com "isolamento de clientes" bloqueiam a ligação entre telemóveis: usar o hotspot do telemóvel-comando e ligar o telemóvel do RV a ele (se o hotspot for o do telemóvel do RV, o link pode mostrar o IP dos dados móveis).

## Falta

- Hotspot e painel da fotografia (T039).
- Passar dados da app ao Unity (fotografias da exposição) e estado do gémeo (MQTT).
