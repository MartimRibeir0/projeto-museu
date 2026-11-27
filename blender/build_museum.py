"""Gera o museu em blockout dentro do Blender e grava museum_master.blend + FBX.

Com o Blender aberto e o addon "MCP for Blender" ativo:
    python blender/send_to_blender.py blender/build_museum.py
Ou sem janela:  blender -b --python blender/build_museum.py
Substitui a cena aberta. Medidas em metros; Y = sentido do percurso, Z = cima.

O museu é montado a partir de 3 módulos, conforme as coleções que o visitante escolhe antes de entrar:
    Sala inicial 8x8 m (nasce aqui; secretária do gémeo digital + 6 quadros)
      -> Corredor: 1 segmento de 8 m por cada 2 coleções, sem quadros, porta a meio à esquerda e/ou à direita
           -> Sala da coleção (máx. 10 quadros), com porta para a sala seguinte da mesma coleção, e assim
              até caberem todos os quadros da coleção.
Regra em layout(); a cena gravada é um exemplo (EXAMPLE) e o Unity repete a regra com os mesmos módulos.

Planta do exemplo (vista de cima):
    [R3][R2][R1]=|C02|                 coleção 3 (23 quadros) à esquerda do 2.º segmento
        [R2][R1]=|C01|=[R1]            coleção 1 (14) à esquerda, coleção 2 (6) à direita
                 [Sala inicial]
"""

import math
import re
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parent.parent  # __file__: injetado por send_to_blender.py ou definido pelo Blender (-b --python)
BLEND = ROOT / "blender" / "museum_master.blend"
EXPORT = ROOT / "blender" / "export"
DOCS = ROOT / "docs" / "blender"
TEX = EXPORT / "textures"  # PNG ao lado dos FBX: o FBX guarda o caminho relativo "textures/..."
TEX_PX = 256  # 1 textura = 1 m (UV em metros), baixa resolução para mobile

H = 3.2  # altura das paredes
T = 0.2  # espessura das paredes
DOOR_W, DOOR_H = 2.0, 2.4
LOBBY = 8.0  # sala inicial LOBBY x LOBBY
COR_W, SEG_L = 4.0, 8.0  # corredor: largura interior e comprimento de cada segmento (2 coleções)
ROOM_W, ROOM_D = 7.6, 10.0  # sala de coleção: largura e fundo entre eixos de parede (cabe ao lado da vizinha: 7,8 < 8)
ROOM_SLOTS = 10  # quadros por sala
EYE = 1.6  # centro dos quadros (altura dos olhos)
FRAME_B, FRAME_D = 0.08, 0.05  # largura e profundidade da moldura
# Moldura-molde (área da fotografia): o Unity estica-a à medida de cada fotografia (MuseumBuilder.Resize).
VARIANTS = {"Landscape": (1.2, 0.9)}
EXAMPLE = [14, 6, 23]  # n.º de quadros de cada coleção escolhida, só para a cena de exemplo e as imagens
SK_H, SK_T = 0.12, 0.02  # rodapé: altura e espessura


def layout(counts):
    """counts: n.º de quadros de cada coleção escolhida, pela ordem. Devolve [(segmento, lado, sala, quadros)]:
    a coleção i fica no segmento i // 2, à esquerda se i for par; cada sala leva até ROOM_SLOTS quadros."""
    out = []
    for i, n in enumerate(counts):
        for r in range(max(1, math.ceil(n / ROOM_SLOTS))):
            out.append((i // 2, "LR"[i % 2], r, min(ROOM_SLOTS, n - r * ROOM_SLOTS)))
    return out


assert layout([14, 6, 23]) == [(0, "L", 0, 10), (0, "L", 1, 4), (0, "R", 0, 6),
                               (1, "L", 0, 10), (1, "L", 1, 10), (1, "L", 2, 3)]
assert layout([10]) == [(0, "L", 0, 10)] and layout([0]) == [(0, "L", 0, 0)]


# ---------- geometria ----------

def box(x0, x1, y0, y1, z0, z1):
    v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
         (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    return v, f


def cyl(c0, c1, a0, a1, r0, r1=None, n=16, axis="z"):
    """Cilindro/cone. axis z: centro (x=c0, y=c1), de z=a0 a a1. axis y: centro (x=c0, z=c1), de y=a0 a a1."""
    r1 = r0 if r1 is None else max(r1, 0.005)
    ring = [(math.cos(2 * math.pi * i / n), math.sin(2 * math.pi * i / n)) for i in range(n)]
    v = [(c0 + r0 * c, c1 + r0 * s, a0) for c, s in ring] + [(c0 + r1 * c, c1 + r1 * s, a1) for c, s in ring]
    f = [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    f += [tuple(range(n - 1, -1, -1)), tuple(range(n, 2 * n))]
    if axis == "y":  # trocar y<->z espelha a geometria: inverter as faces para as normais ficarem para fora
        v = [(x, z, y) for x, y, z in v]
        f = [tuple(reversed(face)) for face in f]
    return v, f


def box_uv(m):
    """UV por projeção na face dominante, 1 unidade UV = 1 m (texturas repetem à escala real)."""
    uv = m.uv_layers.new(name="UVMap")
    for poly in m.polygons:
        ax = max(range(3), key=lambda i: abs(poly.normal[i]))
        a, b = [i for i in range(3) if i != ax]
        for li in poly.loop_indices:
            co = m.vertices[m.loops[li].vertex_index].co
            uv.data[li].uv = (co[a], co[b])


def hidden_face(f):
    """Face nunca vista: base encostada ao chão (z=0), topo encostado ao teto (z=H), fundo da laje e topo do teto."""
    z, nz, eps = f.calc_center_median().z, f.normal.z, 1e-4
    if nz < -0.99:
        return abs(z) < eps or z < -0.1 + eps
    if nz > 0.99:
        return abs(z - H) < eps or z > H + 0.1 - eps
    return False


def mesh(name, parts, cull=True):
    """parts: caixas (x0, x1, y0, y1, z0, z1) ou pares (verts, faces) já feitos, p. ex. de cyl().
    cull: apagar faces escondidas (T035). Só faz sentido com z do mundo; desligar em geometria local (molduras)."""
    verts, faces = [], []
    for p in parts:
        v, f = p if len(p) == 2 else box(*p)
        n = len(verts)
        verts += v
        faces += [tuple(i + n for i in face) for face in f]
    m = bpy.data.meshes.new(name)
    m.from_pydata(verts, [], faces)
    if cull:
        bm = bmesh.new()
        bm.from_mesh(m)
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if hidden_face(f)], context="FACES")
        bm.to_mesh(m)
        bm.free()
    m.validate()
    box_uv(m)
    return m


def obj(name, data, coll, loc=(0, 0, 0), mat=None, parent=None):
    if mat is not None:  # antes de criar o objeto, senão as cópias ficam sem slot de material
        data.materials.append(mat)
    o = bpy.data.objects.new(name, data)
    coll.objects.link(o)
    o.location = loc
    if parent is not None:
        o.parent = parent  # inversa do pai = identidade: loc e geometria ficam no espaço do pai
    return o


def empty(name, coll, parent=None, loc=(0, 0, 0), rot_z=0.0, size=0.5):
    e = obj(name, None, coll, loc=loc, parent=parent)
    e.empty_display_type, e.empty_display_size = "ARROWS", size
    e.rotation_euler = (0, 0, math.radians(rot_z))
    return e


def noise(seed, blob):
    """Ruído gaussiano suave e repetível nas bordas (filtro em frequência), média 0 e desvio 1."""
    n = TEX_PX
    f = np.fft.fft2(np.random.default_rng(seed).normal(size=(n, n)))
    k = np.fft.fftfreq(n)[:, None] ** 2 + np.fft.fftfreq(n)[None, :] ** 2
    r = np.real(np.fft.ifft2(f * np.exp(-k * (2 * np.pi * blob) ** 2 / 2)))
    return (r - r.mean()) / r.std()


def texture(name, rgb):
    """Grava rgb (TEX_PX x TEX_PX x 3, sRGB 0..1; linha 0 = v=0) em TEX/<name>.png e devolve a imagem."""
    n = TEX_PX
    img = bpy.data.images.new(name, n, n)
    img.pixels.foreach_set(np.dstack([np.clip(rgb, 0, 1), np.ones((n, n))]).astype(np.float32).ravel())
    img.filepath_raw, img.file_format = str(TEX / f"{name}.png"), "PNG"
    img.save()
    return img


def plaster_texture():
    t = 1 + 0.012 * noise(1, 6) + 0.008 * noise(2, 1.5)
    return texture("T_Wall", np.dstack([0.91 * t, 0.90 * t, 0.86 * t]))


def wood_texture():
    """Soalho: 5 tábuas de 20 cm por metro ao longo de Y (sentido do percurso), juntas escuras e veio."""
    n = TEX_PX
    v, u = np.mgrid[0:n, 0:n] / n
    plank = np.floor(u * 5).astype(int)
    rng = np.random.default_rng(3)
    tone, offset = rng.uniform(0.85, 1.1, 5)[plank], rng.uniform(0, 1, 5)[plank]
    grain = 1 + 0.06 * np.sin(2 * np.pi * (u * 60 + 1.5 * noise(4, 10)))  # 60 ciclos inteiros: repete na borda
    seam = ((u * 5) % 1 < 0.025) | (((v + offset) % 1) < 0.008)
    t = np.where(seam, 0.45, tone * grain * (1 + 0.04 * noise(5, 3)))
    return texture("T_FloorWood", np.dstack([0.60 * t, 0.44 * t, 0.30 * t]))


def material(name, rgb, rough=0.7, metal=0.0, emit=0.0, tex=None):
    """PBR simples (Base Color/Roughness/Metallic/Emission, textura opcional na Base Color): passa para o Unity."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nodes = m.node_tree.nodes
    bsdf = next(n for n in nodes if n.type == "BSDF_PRINCIPLED").inputs
    bsdf["Base Color"].default_value = (*rgb, 1)
    if tex is not None:
        node = nodes.new("ShaderNodeTexImage")
        node.image, node.location = tex, (-400, 200)
        m.node_tree.links.new(node.outputs["Color"], bsdf["Base Color"])
    bsdf["Roughness"].default_value = rough
    bsdf["Metallic"].default_value = metal
    if emit:
        bsdf["Emission Color"].default_value = (*rgb, 1)
        bsdf["Emission Strength"].default_value = emit
    m.diffuse_color = (*rgb, 1)  # cor usada no viewport/Workbench
    m.roughness, m.metallic = rough, metal
    return m


def sign(name, body, loc, face, coll, mat, size=0.3, parent=None):
    """Texto em relevo (mesh, para ir no FBX) numa parede. face: direção para onde o texto olha ('-y', '+y', '+x', '-x')."""
    cu = bpy.data.curves.new(name, "FONT")
    cu.body, cu.size, cu.align_x, cu.align_y, cu.extrude = body, size, "CENTER", "CENTER", 0.01
    cu.resolution_u = 3  # curvas das letras: 12 por omissão era a maior parte dos vértices da cena (T035)
    tmp = bpy.data.objects.new(name, cu)
    bpy.context.scene.collection.objects.link(tmp)
    bpy.context.view_layer.update()
    me = bpy.data.meshes.new_from_object(tmp.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    bpy.data.objects.remove(tmp)
    bpy.data.curves.remove(cu)
    rot_z = {"-y": 0, "+y": 180, "+x": 90, "-x": -90}[face]
    me.transform(Matrix.Rotation(math.radians(rot_z), 4, "Z") @ Matrix.Rotation(math.radians(90), 4, "X"))
    me.name = name
    box_uv(me)
    return obj(name, me, coll, loc=loc, mat=mat, parent=parent)


def wall_x(x, y0, y1, z0=0.0, z1=H):
    """Parede ao longo de Y centrada na linha x."""
    return (x - T / 2, x + T / 2, y0, y1, z0, z1)


def wall_y(y, x0, x1, z0=0.0, z1=H):
    """Parede ao longo de X centrada na linha y."""
    return (x0, x1, y - T / 2, y + T / 2, z0, z1)


def wall_with_gap(y, x0, x1, gap_w, gap_h=H):
    """Parede em y com abertura centrada (porta ou passagem); acima da abertura fica um lintel."""
    g = gap_w / 2
    parts = [wall_y(y, x0, -g), wall_y(y, g, x1)]
    if gap_h < H:
        parts.append(wall_y(y, -g, g, gap_h, H))
    return parts


def door_wall(along, at, a0, a1, c=0.0):
    """Parede de a0 a a1 com porta (DOOR_W x DOOR_H) centrada em c, e o aro saliente dos dois lados.
    along 'x': parede ao longo de X na linha y=at; 'y': ao longo de Y na linha x=at. Devolve (parede, aro)."""
    def ab(a_0, a_1, p0, p1, z0, z1):
        return (a_0, a_1, p0, p1, z0, z1) if along == "x" else (p0, p1, a_0, a_1, z0, z1)
    d, t = DOOR_W / 2, T / 2
    wall = [ab(a0, c - d, at - t, at + t, 0, H), ab(c + d, a1, at - t, at + t, 0, H),
            ab(c - d, c + d, at - t, at + t, DOOR_H, H)]
    trim = [ab(c - d - 0.1, c - d, at - 0.15, at + 0.15, 0, DOOR_H + 0.1),
            ab(c + d, c + d + 0.1, at - 0.15, at + 0.15, 0, DOOR_H + 0.1),
            ab(c - d - 0.1, c + d + 0.1, at - 0.15, at + 0.15, DOOR_H, DOOR_H + 0.1)]
    return wall, trim


# ---------- cena ----------

def reset():
    for coll in (bpy.data.objects, bpy.data.meshes, bpy.data.materials, bpy.data.cameras,
                 bpy.data.lights, bpy.data.curves, bpy.data.collections, bpy.data.images):
        for item in list(coll):
            coll.remove(item)
    s = bpy.context.scene
    s.unit_settings.system = "METRIC"
    s.unit_settings.scale_length = 1.0
    s.unit_settings.length_unit = "METERS"
    cols = {}
    for name in ("Architecture", "Frames", "Props", "DigitalTwin", "Annotations", "_Templates"):
        c = bpy.data.collections.new(name)
        s.collection.children.link(c)
        cols[name] = c
    return cols


def build_frame_template(name, w, h, coll, mats):
    """Moldura virada para -Y, origem no centro da fotografia; a fotografia é um objeto filho separado."""
    b, d = FRAME_B, FRAME_D
    x, z = w / 2, h / 2
    frame = obj(f"Frame_{name}", mesh(f"Frame_{name}", [
        (-x - b, x + b, -d / 2, d / 2, z, z + b),        # topo
        (-x - b, x + b, -d / 2, d / 2, -z - b, -z),      # base
        (-x - b, -x, -d / 2, d / 2, -z, z),              # esquerda
        (x, x + b, -d / 2, d / 2, -z, z),                # direita
        (-x, x, d / 2 - 0.01, d / 2, -z, z),             # fundo
    ], cull=False), coll, mat=mats["frame"])
    m = bpy.data.meshes.new(f"Photo_{name}")
    m.from_pydata([(-x, 0, -z), (x, 0, -z), (x, 0, z), (-x, 0, z)], [], [(0, 1, 2, 3)])  # normal -Y
    uv = m.uv_layers.new(name="UVMap")
    for loop, co in zip(uv.data, [(0, 0), (1, 0), (1, 1), (0, 1)]):
        loop.uv = co
    obj(f"Photo_{name}", m, coll, loc=(0, d / 2 - 0.015, 0), mat=mats["photo"], parent=frame)
    frame["aspect"] = round(w / h, 3)
    return frame


def place_frame(template, slot, coll, tag):
    """Cópia da moldura e da fotografia, filha do slot. Mesh própria: o export FBX perde o material em meshes partilhadas."""
    f = template.copy()
    f.data = template.data.copy()
    f.name = f"{tag}_{template.name}"
    coll.objects.link(f)
    f.parent, f.location = slot, (0, 0, 0)
    for child in template.children:
        c = child.copy()
        c.data = child.data.copy()
        c.name = f"{tag}_{child.name}"
        coll.objects.link(c)
        c.parent = f
    return f


def text(body, loc, coll, mat, size=0.8):
    cu = bpy.data.curves.new(body, "FONT")
    cu.body, cu.size, cu.align_x = body, size, "CENTER"
    return obj(f"Label_{body}", cu, coll, loc=(loc[0], loc[1], 0.02), mat=mat)


class Builder:
    """Constrói os módulos. Geometria de cada módulo em coordenadas locais; os filhos herdam a pose do pai."""

    def __init__(self, cols):
        self.cols = cols
        self.mats = {
            "wall": material("Wall", (0.85, 0.84, 0.80), tex=plaster_texture()),
            "floor": material("Floor", (0.45, 0.33, 0.22), tex=wood_texture()),
            "ceiling": material("Ceiling", (0.95, 0.95, 0.95)),
            "frame": material("FrameWood", (0.18, 0.12, 0.08)),
            "photo": material("PhotoPlaceholder", (0.55, 0.6, 0.65)),
            "label": material("Label", (0.8, 0.1, 0.1)),
            "skirting": material("Skirting", (0.22, 0.22, 0.24), rough=0.5),
            "runner": material("Runner", (0.42, 0.1, 0.12), rough=0.9),
            "lamp": material("LampEmit", (1.0, 0.95, 0.82), rough=0.3, emit=4.0),
            "metal": material("Metal", (0.62, 0.63, 0.65), rough=0.3, metal=1.0),
            "sign": material("Sign", (0.12, 0.12, 0.13), rough=0.4),
            "plaque": material("Plaque", (0.93, 0.91, 0.86), rough=0.6),
            "pot": material("Pot", (0.62, 0.36, 0.24)),
            "plant": material("Plant", (0.16, 0.38, 0.17), rough=0.8),
            "desk": material("DeskTop", (0.78, 0.74, 0.68), rough=0.5),
        }
        self.templates = {}
        for i, (name, (w, h)) in enumerate(VARIANTS.items()):
            self.templates[name] = build_frame_template(name, w, h, cols["_Templates"], self.mats)
            self.templates[name].location = (50, 2 + 2 * i, EYE)  # prateleira fora do museu
        self.order = list(VARIANTS)

    def part(self, name, parts, coll, mat, parent, cull=True):
        return obj(name, mesh(name, parts, cull), coll, mat=self.mats[mat], parent=parent)

    def skirting(self, name, segs, coll, parent):
        """Rodapé: segs são retângulos (x0, x1, y0, y1) em planta, já encostados à face interior da parede."""
        return self.part(name, [(*s, 0, SK_H) for s in segs], coll, "skirting", parent)

    def wall_piece(self, name, parts, skirt, coll, parent, trim=None):
        """Parede trocável (com porta ou cheia): rodapé e aro são filhos, para irem e virem com ela."""
        w = self.part(name, parts, coll, "wall", parent)
        self.skirting(f"{name}_Skirting", skirt, coll, w)
        if trim:
            self.part(f"{name}_Trim", trim, coll, "frame", w)
        return w

    def slot(self, name, coll, parent, loc, rot_z, variant=None):
        """Empty onde o Unity põe a moldura (já rodado: -Y para a sala), com luz de quadro e placa.
        Em coordenadas do slot: X ao longo da parede, -Y para a sala, parede em y=+FRAME_D/2."""
        s = empty(name, coll, parent, loc, rot_z, size=0.3)
        s["slot"] = name
        w = FRAME_D / 2
        self.part(f"{name}_PictureLight", [
            (-0.3, 0.3, -0.16, -0.1, 0.78, 0.83),  # barra de luz
            (-0.2, -0.17, -0.1, w, 0.8, 0.82), (0.17, 0.2, -0.1, w, 0.8, 0.82),  # braços até à parede
        ], coll, "metal", s, cull=False)
        self.part(f"{name}_Plaque", [(0.78, 1.0, w - 0.012, w, -0.4, -0.26)], coll, "plaque", s, cull=False)
        if variant:
            place_frame(self.templates[variant], s, coll, name)
        return s

    def floor_walls(self, name, floor, walls, coll, parent=None, loc=(0, 0, 0)):
        """Chão e paredes numa só mesh com 2 materiais (chão a castanho, paredes a branco)."""
        m = mesh(name, [floor, *walls])
        m.materials.append(self.mats["wall"])
        m.materials.append(self.mats["floor"])
        for poly in m.polygons:
            poly.material_index = 1 if poly.normal.z > 0.5 and poly.center.z < 0.01 else 0
        return obj(name, m, coll, loc=loc, parent=parent)

    # ----- sala inicial -----

    def lobby(self, n_frames=6):
        """Sala onde o visitante nasce: y 0..LOBBY, passagem para o corredor em y=LOBBY.
        Secretária do gémeo digital encostada à parede do fundo; 3 quadros em cada parede lateral."""
        arch, props, twin, frames = (self.cols[k] for k in ("Architecture", "Props", "DigitalTwin", "Frames"))
        hx = LOBBY / 2
        root = self.part("Lobby", [(-hx, hx, 0, LOBBY, -0.1, 0)], arch, "floor", None)
        self.part("Lobby_Ceiling", [(-hx, hx, 0, LOBBY, H, H + 0.1)], arch, "ceiling", root)
        self.part("Lobby_Walls", [
            wall_y(0, -hx - T / 2, hx + T / 2),
            *wall_with_gap(LOBBY, -hx - T / 2, hx + T / 2, COR_W, H - 0.5),  # lintel marca a entrada nas exposições
            wall_x(-hx, 0, LOBBY), wall_x(hx, 0, LOBBY),
        ], arch, "wall", root)
        ix, g = hx - T / 2, COR_W / 2 + T / 2  # face interior das paredes laterais; fim das paredes do corredor
        self.skirting("Lobby_Skirting", [
            (-ix, ix, T / 2, T / 2 + SK_T),
            (-ix, -g, LOBBY - T / 2 - SK_T, LOBBY - T / 2), (g, ix, LOBBY - T / 2 - SK_T, LOBBY - T / 2),
            (-ix, -ix + SK_T, T / 2, LOBBY - T / 2), (ix - SK_T, ix, T / 2, LOBBY - T / 2),
        ], arch, root)
        self.part("Lobby_CeilingLights", [cyl(x, y, H - 0.04, H, 0.25, n=24) for x in (-2, 2) for y in (2, 6)],
                  arch, "lamp", root)
        sign("Sign_Title", "Museu Virtual", (0, T / 2 + 0.015, 2.5), "+y", props, self.mats["sign"], size=0.45, parent=root)
        sign("Sign_Exhibitions", "Exposições", (0, LOBBY - T / 2 - 0.015, H - 0.25), "-y", props, self.mats["sign"],
             parent=root)
        for side, x in (("L", -ix + 0.45), ("R", ix - 0.45)):
            pot = self.part(f"Lobby_Plant_{side}", [cyl(x, LOBBY - 0.7, 0, 0.45, 0.2, 0.24)], props, "pot", root)
            self.part(f"Lobby_Plant_{side}_Leaves", [cyl(x, LOBBY - 0.7, 0.45, 1.7, 0.32, 0.02, n=8)], props, "plant", pot)

        # Secretária do gémeo digital (o gémeo desenvolve-se aqui mais tarde); Twin_DeskAnchor marca o tampo.
        y0, y1 = T / 2 + 0.1, T / 2 + 0.9
        desk = self.part("Twin_Desk", [(-0.75, -0.7, y0, y1, 0, 0.72), (0.7, 0.75, y0, y1, 0, 0.72),  # ilhargas
                                       (-0.7, 0.7, y0, y0 + 0.03, 0.3, 0.72)], twin, "frame", root)   # painel de fundo
        self.part("Twin_Desk_Top", [(-0.8, 0.8, y0 - 0.02, y1 + 0.02, 0.72, 0.76)], twin, "desk", desk)
        anchor = empty("Twin_DeskAnchor", twin, root, (0, (y0 + y1) / 2, 0.76), size=0.2)
        anchor["twin"] = "desk"
        cy = y1 + 0.45
        self.part("Lobby_Chair", [
            (-0.22, 0.22, cy - 0.2, cy + 0.2, 0.43, 0.47),  # assento
            *[(x, x + 0.04, y, y + 0.04, 0, 0.43) for x in (-0.2, 0.16) for y in (cy - 0.18, cy + 0.14)],  # pernas
            (-0.22, 0.22, cy + 0.16, cy + 0.2, 0.47, 0.9),  # costas (do lado do visitante, de frente para a mesa)
        ], props, "metal", root)
        empty("Lobby_Spawn", arch, root, (0, 4.0, 0), size=0.6)  # onde o visitante nasce, a olhar para +Y (corredor)

        x = -ix + FRAME_D / 2
        for i, y in enumerate((2, 4, 6)):
            self.slot(f"Lobby_Slot_{i + 1:02d}", frames, root, (x, y, EYE), 90, self.order[0])
        for i, y in enumerate((6, 4, 2)):
            self.slot(f"Lobby_Slot_{i + 4:02d}", frames, root, (-x, y, EYE), -90, self.order[0])
        return root

    # ----- segmento de corredor -----

    def corridor(self, tag, coll, loc, left, right, end):
        """Segmento de SEG_L m sem quadros, de y=0 a y=SEG_L local (encaixam sem folgas), portas a meio.
        left/right: 'Door', 'Solid' ou 'Both' (as duas variantes, para o módulo exportado; o Unity apaga uma).
        end: parede do fundo (último segmento). Tag_Anchor_L/R: pose da 1.ª sala da coleção desse lado."""
        mx, c = COR_W / 2, SEG_L / 2
        root = self.part(tag, [(-mx - T / 2, mx + T / 2, 0, SEG_L, -0.1, 0)], coll, "floor", None)
        root.location = loc
        self.part(f"{tag}_Ceiling", [(-mx - T / 2, mx + T / 2, 0, SEG_L, H, H + 0.1)], coll, "ceiling", root)
        self.part(f"{tag}_Runner", [(-0.8, 0.8, 0, SEG_L, 0, 0.008)], coll, "runner", root)
        self.part(f"{tag}_CeilingLight", [(-0.12, 0.12, 0.6, SEG_L - 0.6, H - 0.04, H)], coll, "lamp", root)
        d = DOOR_W / 2 + 0.1  # rodapé pára no aro
        for side, kind, s in (("L", left, -1), ("R", right, 1)):
            x, ix = s * mx, s * (mx - T / 2)
            sk = (min(ix, ix - s * SK_T), max(ix, ix - s * SK_T))  # faixa do rodapé junto à face interior
            if kind in ("Door", "Both"):
                wall, trim = door_wall("y", x, 0, SEG_L, c)
                self.wall_piece(f"{tag}_Wall_{side}_Door", wall, [(*sk, 0, c - d), (*sk, c + d, SEG_L)], coll, root, trim)
                a = empty(f"{tag}_Anchor_{side}", coll, root, (x, c, 0), 90 if side == "L" else -90)
                a["door"] = side
            if kind in ("Solid", "Both"):
                self.wall_piece(f"{tag}_Wall_{side}_Solid", [wall_x(x, 0, SEG_L)], [(*sk, 0, SEG_L)], coll, root)
        if end:
            iy = SEG_L - T / 2
            self.wall_piece(f"{tag}_EndWall", [wall_y(SEG_L, -mx - T / 2, mx + T / 2)],
                            [(-mx + T / 2, mx - T / 2, iy - SK_T, iy)], coll, root)
        return root

    # ----- sala de coleção -----

    def room(self, tag, coll, fcoll, parent, far, n_frames=0):
        """Sala de coleção em coordenadas locais: entrada em y=0 (eixo da parede com a porta, que é do corredor
        ou da sala anterior), fundo em y=ROOM_D. Sem parede de entrada: encosta à parede com porta de quem a precede.
        far: parede do fundo 'Door' (há sala seguinte, em Tag_Anchor_Next), 'Solid' (última) ou 'Both'.
        Slots 01-04 parede esquerda, 05-06 fundo (ladeiam a porta), 07-10 parede direita: volta pela sala."""
        hw, t = ROOM_W / 2, T / 2
        iw, back = hw - t, ROOM_D - t  # faces interiores: paredes laterais e fundo
        root = self.floor_walls(tag, (-hw - t, hw + t, t, ROOM_D + t, -0.1, 0),
                                [wall_x(-hw, t, ROOM_D), wall_x(hw, t, ROOM_D)], coll, parent)
        self.part(f"{tag}_Ceiling", [(-hw - t, hw + t, t, ROOM_D + t, H, H + 0.1)], coll, "ceiling", root)
        self.skirting(f"{tag}_Skirting", [(-iw, -iw + SK_T, t, back), (iw - SK_T, iw, t, back)], coll, root)
        self.part(f"{tag}_CeilingLights", [cyl(x, y, H - 0.04, H, 0.25, n=24) for x in (-1.8, 1.8) for y in (3, 7)],
                  coll, "lamp", root)
        self.part(f"{tag}_Bench", [
            (-0.2, 0.2, ROOM_D / 2 - 1.0, ROOM_D / 2 + 1.0, 0.38, 0.45),  # assento
            (-0.15, 0.15, ROOM_D / 2 - 0.9, ROOM_D / 2 - 0.8, 0, 0.38), (-0.15, 0.15, ROOM_D / 2 + 0.8, ROOM_D / 2 + 0.9, 0, 0.38),
        ], coll, "frame", root)
        d = DOOR_W / 2 + 0.1
        if far in ("Door", "Both"):
            wall, trim = door_wall("x", ROOM_D, -hw - t, hw + t)
            self.wall_piece(f"{tag}_FarWall_Door", wall, [(-iw, -d, back - SK_T, back), (d, iw, back - SK_T, back)],
                            coll, root, trim)
            empty(f"{tag}_Anchor_Next", coll, root, (0, ROOM_D, 0))
        if far in ("Solid", "Both"):
            self.wall_piece(f"{tag}_FarWall_Solid", [wall_y(ROOM_D, -hw - t, hw + t)], [(-iw, iw, back - SK_T, back)],
                            coll, root)
        x = iw - FRAME_D / 2
        poses = ([(-x, y, 90) for y in (2, 4, 6, 8)] + [(-2.6, back - FRAME_D / 2, 0), (2.6, back - FRAME_D / 2, 0)]
                 + [(x, y, -90) for y in (8, 6, 4, 2)])
        for i, (px, py, rz) in enumerate(poses):
            variant = self.order[0] if i < n_frames else None
            self.slot(f"{tag}_Slot_{i + 1:02d}", fcoll, root, (px, py, EYE), rz, variant)
        return root


def build(counts):
    cols = reset()
    b = Builder(cols)
    arch, frames, notes, tmpl = (cols[k] for k in ("Architecture", "Frames", "Annotations", "_Templates"))

    # Módulos para o Unity, com todas as variantes de parede e slots vazios, longe do museu (não aparecem nos renders).
    tpl_corridor = b.corridor("Corridor", tmpl, (60, 0, 0), "Both", "Both", True)
    tpl_room = b.room("Room", tmpl, tmpl, None, "Both")
    tpl_room.location = (75, 0, 0)

    # Exemplo montado pela regra de layout().
    lobby = b.lobby()
    plan = layout(counts)
    n_seg = plan[-1][0] + 1
    segs = []
    for s in range(n_seg):
        sides = {side for seg, side, _, _ in plan if seg == s}
        segs.append(b.corridor(f"C{s + 1:02d}", arch, (0, LOBBY + s * SEG_L, 0),
                               "Door" if "L" in sides else "Solid", "Door" if "R" in sides else "Solid", s == n_seg - 1))
    rooms, prev = [], None
    for k, (s, side, r, n) in enumerate(plan):
        last = k + 1 == len(plan) or plan[k + 1][2] == 0  # última sala da coleção
        parent = bpy.data.objects[f"C{s + 1:02d}_Anchor_{side}"] if r == 0 else bpy.data.objects[f"{prev}_Anchor_Next"]
        prev = f"C{s + 1:02d}_{side}_R{r + 1}"
        rooms.append(b.room(prev, arch, frames, parent, "Solid" if last else "Door", n))

    # Anotações: só para a planta e para validar a escala; não vão para o FBX.
    bpy.context.view_layer.update()
    text("Sala inicial", (0, LOBBY / 2 + 1.2), notes, b.mats["label"])
    for i, n in enumerate(counts):
        first = bpy.data.objects[f"C{i // 2 + 1:02d}_{'LR'[i % 2]}_R1"]
        p = first.matrix_world @ Vector((1.8, ROOM_D / 2, 0))  # ao lado do banco
        text(f"Coleção {i + 1} ({n})", (p.x, p.y), notes, b.mats["label"], size=0.6)
    obj("Visitor_1m75", mesh("Visitor_1m75", [(-0.25, 0.25, -0.15, 0.15, 0, 1.75)]), notes,
        loc=(1.5, 4.0, 0), mat=b.mats["label"])

    # Pivôs úteis (T033): móveis pousados pela base.
    for name in ("Twin_Desk", "Lobby_Chair", "Lobby_Plant_L", "Lobby_Plant_R", "C01_L_R1_Bench", "Room_Bench"):
        set_origin(bpy.data.objects[name], "base")
    return lobby, segs, rooms, tpl_corridor, tpl_room


def set_origin(o, where):
    """Origem no centro da caixa envolvente (base/top: no fundo/topo) sem mexer no objeto no mundo.
    Supõe objeto sem rotação/escala (como todos os gerados aqui); os filhos são compensados."""
    co = np.array([v.co for v in o.data.vertices])
    lo, hi = co.min(axis=0), co.max(axis=0)
    p = Vector((lo + hi) / 2)
    p.z = {"base": lo[2], "top": hi[2], "center": p.z}[where]
    o.data.transform(Matrix.Translation(-p))
    o.location += p
    for c in o.children:
        c.location -= p


# ---------- renders e exports ----------

def render(cam_data, loc, target, path, res, hide):
    """Render Workbench da câmara em loc a olhar para target (ou rotação Euler, se target for um tuplo de 3 ângulos)."""
    s = bpy.context.scene
    cam = bpy.data.objects.new("Cam", cam_data)
    s.collection.objects.link(cam)
    cam.location = loc
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler() \
        if isinstance(target, Vector) else target
    s.camera = cam
    s.render.engine = "BLENDER_WORKBENCH"
    s.display.shading.light = "STUDIO"
    s.display.shading.color_type = "TEXTURE"  # textura onde há, cor do material no resto
    s.display.shading.show_cavity = True
    s.render.resolution_x, s.render.resolution_y = res
    s.render.resolution_percentage = 100
    s.render.filepath = str(path)
    s.render.image_settings.file_format, s.render.image_settings.quality = "JPEG", 85
    hidden = [o for o in bpy.data.objects if hide(o)]
    for o in hidden:
        o.hide_render = True
    bpy.ops.render.render(write_still=True)
    for o in hidden:
        o.hide_render = False
    bpy.data.objects.remove(cam)
    bpy.data.cameras.remove(cam_data)


def in_coll(o, *names):
    return any(c.name in names for c in o.users_collection)


def check_meshes(objects):
    """T033: escala/rotação aplicadas e malhas limpas (sem faces degeneradas, duplicadas ou com normais trocadas).
    As rotações das salas vêm dos empties de ligação (Anchor_*); as meshes ficam sem rotação local."""
    errors = []
    for o in objects:
        if o.type != "MESH":
            continue
        if any(abs(s - 1) > 1e-6 for s in o.scale) or any(abs(r) > 1e-6 for r in o.rotation_euler):
            errors.append(f"{o.name}: transformação não aplicada")
        bm = bmesh.new()
        bm.from_mesh(o.data)
        if any(f.calc_area() < 1e-8 for f in bm.faces):
            errors.append(f"{o.name}: face degenerada")
        keys = [frozenset(tuple(round(c, 5) for c in v.co) for v in f.verts) for f in bm.faces]
        if len(keys) != len(set(keys)):
            errors.append(f"{o.name}: faces duplicadas")
        # Com normais coerentes, as duas faces de uma aresta percorrem-na em sentidos opostos.
        if any(len(e.link_loops) == 2 and e.link_loops[0].vert == e.link_loops[1].vert for e in bm.edges):
            errors.append(f"{o.name}: normais incoerentes")
        bm.free()
    return errors


def check_layout(rooms):
    """As salas de coleções diferentes e as salas seguidas não se sobrepõem (planta, com folga de 1 cm)."""
    boxes = []
    for r in rooms:
        bb = world_bbox(r)
        boxes.append((r.name, bb[0] + 0.01, bb[3] - 0.01, bb[1] + 0.01, bb[4] - 0.01))
    lobby = world_bbox(bpy.data.objects["Lobby_Walls"])
    boxes.append(("Lobby", lobby[0], lobby[3], lobby[1], lobby[4] - 0.11))  # sem a parede partilhada com o corredor
    errors = []
    for i, a in enumerate(boxes):
        for c in boxes[i + 1:]:  # (nome, x0, x1, y0, y1)
            if a[1] < c[2] and c[1] < a[2] and a[3] < c[4] and c[3] < a[4]:
                errors.append(f"{a[0]} sobrepõe {c[0]}")
    return errors


def world_bbox(o):
    pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
    return Vector([min(p[i] for p in pts) for i in range(3)] + [max(p[i] for p in pts) for i in range(3)])


def base_name(name):
    return re.sub(r"\.\d{3}$", "", name)


def check_fbx(path, originals):
    """T034: reimporta o FBX ao lado da cena e compara nomes, hierarquia, posição/tamanho, faces, materiais,
    texturas e propriedades. Apaga tudo o que importou."""
    before = {k: set(getattr(bpy.data, k)) for k in ("objects", "meshes", "materials", "images")}
    vl = bpy.context.view_layer
    coll = bpy.data.collections.new("_FBXCheck")
    bpy.context.scene.collection.children.link(coll)
    active = vl.active_layer_collection
    vl.active_layer_collection = vl.layer_collection.children[coll.name]
    errors = []
    try:
        bpy.ops.import_scene.fbx(filepath=str(path), use_custom_props=True)
        vl.update()
        got = {base_name(o.name): o for o in coll.objects}
        if len(got) != len(originals):
            errors.append(f"{path.name}: {len(got)} objetos importados, esperados {len(originals)}")
        for o in originals:
            g = got.get(o.name)
            if g is None:
                errors.append(f"{path.name}: falta {o.name}")
                continue
            if o.parent in originals and (g.parent is None or base_name(g.parent.name) != o.parent.name):
                errors.append(f"{o.name}: pai errado")
            for k in ("aspect", "slot", "door", "twin"):
                if k in o and g.get(k) != o[k]:
                    errors.append(f"{o.name}: propriedade {k} perdida")
            if o.type != "MESH":
                continue
            if (world_bbox(g) - world_bbox(o)).length > 1e-3:
                errors.append(f"{o.name}: posição/escala/eixos diferentes")
            if len(g.data.polygons) != len(o.data.polygons):
                errors.append(f"{o.name}: {len(g.data.polygons)} faces, esperadas {len(o.data.polygons)}")
            want = [m.name for m in o.data.materials]
            have = [base_name(m.name) for m in g.data.materials if m]
            if have != want:
                errors.append(f"{o.name}: materiais {have}, esperados {want}")
            for m in g.data.materials:
                src = bpy.data.materials.get(base_name(m.name))
                needs = src is not None and any(n.type == "TEX_IMAGE" for n in src.node_tree.nodes)
                if needs and not any(n.type == "TEX_IMAGE" and n.image and n.image.has_data
                                     for n in m.node_tree.nodes):
                    errors.append(f"{o.name}: textura de {src.name} não encontrada")
    finally:
        vl.active_layer_collection = active
        for k, old in before.items():
            data = getattr(bpy.data, k)
            for item in set(data) - old:
                data.remove(item)
        bpy.data.collections.remove(coll)
    return errors


def export(path, objects, zero=None):
    """Exporta para Unity (Y-up, escala 1 = 1 m) e verifica reimportando. `zero`: raiz posta na origem."""
    saved = zero.location.copy() if zero else None
    if zero:
        zero.location = (0, 0, 0)
    bpy.context.view_layer.update()
    for o in bpy.context.view_layer.objects:
        o.select_set(o in objects)
    bpy.ops.export_scene.fbx(
        filepath=str(path), use_selection=True, object_types={"MESH", "EMPTY"},
        # bake_space_transform=True deita as fotografias e roda as molduras dos slots (detetado por check_fbx);
        # a conversão de eixos faz-se no Unity com "Bake Axis Conversion" no import do modelo.
        apply_scale_options="FBX_SCALE_ALL", axis_forward="-Z", axis_up="Y", bake_space_transform=False,
        use_custom_props=True, mesh_smooth_type="FACE", add_leaf_bones=False, path_mode="RELATIVE",
    )
    errors = check_fbx(path, objects)
    if zero:
        zero.location = saved
    return errors


def tree(root):
    return [root, *root.children_recursive]


def main():
    TEX.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)
    lobby, segs, rooms, tpl_corridor, tpl_room = build(EXAMPLE)
    bpy.context.view_layer.update()
    museum = [o for o in bpy.data.objects if not in_coll(o, "Annotations", "_Templates")]
    errors = check_meshes(museum) + check_meshes(tree(tpl_corridor) + tree(tpl_room)) + check_layout(rooms)

    # Planta: câmara ortográfica de cima, a abranger o exemplo todo.
    floors = [world_bbox(o) for o in [lobby, *segs, *rooms]]
    x0, y0 = min(b[0] for b in floors), min(b[1] for b in floors)
    x1, y1 = max(b[3] for b in floors), max(b[4] for b in floors)
    plan = bpy.data.cameras.new("Plan")
    plan.type, plan.ortho_scale = "ORTHO", max(x1 - x0, y1 - y0) + 1.0
    plan.clip_start = 30 - 2.6  # corte horizontal a 2,6 m, como numa planta: lintéis e tetos não tapam as passagens
    px = 1800
    res = (px, round(px * (y1 - y0 + 1) / (x1 - x0 + 1))) if x1 - x0 >= y1 - y0 else (round(px * (x1 - x0 + 1) / (y1 - y0 + 1)), px)
    no_annot = lambda o: in_coll(o, "Annotations", "_Templates")
    render(plan, ((x0 + x1) / 2, (y0 + y1) / 2, 30), (0, 0, 0), DOCS / "planta.jpg", res,
           hide=lambda o: "Ceiling" in o.name or in_coll(o, "_Templates"))
    # Visitor onde nasce, a olhar para o corredor; secretária; 1.ª sala de coleção vista da entrada.
    view = bpy.data.cameras.new("View")
    view.lens = 18
    render(view, (0, 2.0, EYE), Vector((0, 14, EYE)), DOCS / "blockout.jpg", (1600, 900), no_annot)
    desk = bpy.data.cameras.new("Desk")
    desk.lens = 18
    render(desk, (2.6, 5.6, EYE), Vector((0, 0.6, 1.0)), DOCS / "secretaria.jpg", (1600, 900), no_annot)
    room_cam = bpy.data.cameras.new("Room")
    room_cam.lens = 16
    r = rooms[0].matrix_world
    render(room_cam, r @ Vector((0, 0.4, EYE)), r @ Vector((0, ROOM_D, 1.4)), DOCS / "sala.jpg", (1600, 900), no_annot)

    errors += export(EXPORT / "museum_blockout.fbx", museum)
    errors += export(EXPORT / "lobby.fbx", tree(lobby))
    errors += export(EXPORT / "corridor_segment.fbx", tree(tpl_corridor), zero=tpl_corridor)
    errors += export(EXPORT / "gallery_room.fbx", tree(tpl_room), zero=tpl_room)
    for name in VARIANTS:
        t = bpy.data.objects[f"Frame_{name}"]
        errors += export(EXPORT / f"frame_{name.lower()}.fbx", tree(t), zero=t)
    if errors:
        raise RuntimeError("verificação falhou:\n" + "\n".join(errors))

    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND))
    verts = sum(len(o.data.vertices) for o in museum if o.type == "MESH")
    tris = sum(len(p.vertices) - 2 for o in museum if o.type == "MESH" for p in o.data.polygons)
    return (f"ok: exemplo {EXAMPLE} = {len(segs)} segmentos de corredor, {len(rooms)} salas; {len(museum)} objetos, "
            f"{verts} vértices, {tris} triângulos; meshes, planta e FBX verificados; gravado {BLEND.name}")


result = main()  # send_to_blender.py devolve `result`
print(result)
