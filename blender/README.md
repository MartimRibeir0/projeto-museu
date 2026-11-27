# blender

Museu em blockout (RVA, T024–T035), gerado por script para ser reproduzível e montado por módulos.

## Planta

O visitante escolhe, antes de entrar em RV, a coleção ou coleções que quer ver. O museu monta-se assim (`layout()` em `build_museum.py`):

- **Sala inicial** 8×8 m, onde se nasce (`Lobby_Spawn`, a olhar para o corredor): secretária do gémeo digital (`Twin_Desk`, tampo marcado por `Twin_DeskAnchor`) e 6 quadros (`Lobby_Slot_01..06`).
- **Corredor**: 1 segmento de 8 m por cada 2 coleções, sem quadros, com uma porta a meio à esquerda e outra à direita. A coleção *i* fica no segmento *i* // 2, à esquerda se *i* for par. Com 1 coleção (ou um número ímpar), o último segmento só tem a porta da esquerda. O último segmento fecha com parede ao fundo.
- **Sala de coleção** 7,6×10 m, máx. 10 quadros (`Slot_01..04` parede esquerda, `05..06` fundo, `07..10` parede direita). Se a coleção tiver mais de 10, a parede do fundo tem porta para outra sala igual, e assim até caberem todos.

A cena gravada é um exemplo com 3 coleções de 14, 6 e 23 quadros (`EXAMPLE`): 2 segmentos, 2 + 1 + 3 salas.

| Ficheiro | O que é |
|----------|---------|
| `build_museum.py` | Gera a cena, grava `museum_master.blend`, os FBX e os renders |
| `send_to_blender.py` | Envia um script ao Blender aberto (addon "MCP for Blender", porta 9876) |
| `museum_master.blend` | Fonte (Git LFS) |
| `export/museum_blockout.fbx` | Exemplo montado, para referência |
| `export/lobby.fbx` | Sala inicial (com 6 molduras nos slots) |
| `export/corridor_segment.fbx` | Segmento de corredor com **todas** as variantes: `Corridor_Wall_{L,R}_{Door,Solid}` e `Corridor_EndWall`; o Unity apaga as que não usa |
| `export/gallery_room.fbx` | Sala de coleção com `Room_FarWall_{Door,Solid}` (idem) e 10 slots vazios |
| `export/frame_landscape.fbx` | Moldura-molde (fotografia 1,2×0,9 m no filho `Photo_*`, UV 0..1); o Unity estica-a à medida de cada fotografia |
| `export/textures/T_Wall.png`, `T_FloorWood.png` | Texturas 256×256 geradas pelo script (1 textura = 1 m, repetem sem costura) |

Renders: `docs/blender/planta.jpg` (planta, corte a 2,6 m), `blockout.jpg` (onde se nasce), `secretaria.jpg` e `sala.jpg` (1.ª sala de coleção).

O script verifica-se a si próprio e falha se algo estiver mal:

- regra de layout (asserts);
- malhas: escala/rotação aplicadas, sem faces degeneradas ou duplicadas, normais coerentes;
- planta: salas sem sobreposições;
- FBX: reimporta cada ficheiro e compara nomes, hierarquia, posição/tamanho, faces, materiais, texturas e propriedades (`aspect`, `slot`, `door`, `twin`).

## Refazer

Na raiz do repositório, com o Blender 5.3:

- aberto, com o addon "MCP for Blender": `python blender/send_to_blender.py blender/build_museum.py` (**substitui a cena aberta**);
- ou sem janela: `blender -b --factory-startup --python blender/build_museum.py`.

Medidas no topo de `build_museum.py`.

## Ligar módulos (para o Unity)

- Metros; Y = sentido do percurso, Z = cima. Sala inicial de y=0 a 8; o 1.º segmento começa em y=8, o segmento *k* em y = 8 + 8*k*.
- Segmento: origem no início, a meio da largura. `Corridor_Anchor_L/R` (propriedade `door`) é a pose da 1.ª sala desse lado: pôr a sala como filha, com transformação nula.
- Sala: origem na porta de entrada, ao nível do chão, +Y para dentro. Não tem parede de entrada (encosta à parede com porta de quem a precede). `Room_Anchor_Next` é a pose da sala seguinte.
- Moldura: origem no centro da fotografia, frente virada para -Y. Slots (empties, propriedade `slot`) já estão rodados: basta pôr a moldura como filha do slot com transformação nula.
- Pivôs: móveis com a origem na base.
- FBX para Unity: escala 1 = 1 m, Y-up, -Z forward, propriedades personalizadas incluídas, texturas por caminho relativo (`textures/`). **No Unity, ativar "Bake Axis Conversion"** no import do modelo: o `bake_space_transform` do Blender estraga objetos aninhados (fotografias e molduras dos slots).
- Para o Unity encontrar as texturas, copiar a pasta `export/` inteira (FBX + `textures/`).

## Git LFS

`.blend` e `.fbx` estão em Git LFS. Instalar uma vez: `git lfs install`. Sem isso, o clone traz só ponteiros de texto.
