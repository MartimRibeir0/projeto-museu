"""Gera o museu em blockout (T024–T035) dentro do Blender aberto e grava museum_master.blend + FBX.

Correr com o Blender aberto e o addon "MCP for Blender" ativo:
    python blender/send_to_blender.py blender/build_museum.py
Substitui a cena aberta. Medidas em metros; Y = sentido do percurso, Z = cima.

Planta (vista de cima, entrada em y=0):
    Entrada 8x8 m  ->  Corredor N módulos de 4x4 m  ->  Sala do gémeo digital 6x6 m
"""

import math
import re
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parent.parent  # __file__ é injetado por send_to_blender.py
BLEND = ROOT / "blender" / "museum_master.blend"
EXPORT = ROOT / "blender" / "export"
DOCS = ROOT / "docs" / "blender"
TEX = EXPORT / "textures"  # PNG ao lado dos FBX: o FBX guarda o caminho relativo "textures/..."
TEX_PX = 256  # 1 textura = 1 m (UV em metros), baixa resolução para mobile

H = 3.2  # altura das paredes
T = 0.2  # espessura das paredes
DOOR_W, DOOR_H = 2.0, 2.4
HALL = 8.0  # entrada HALL x HALL
MOD_L, MOD_W = 4.0, 4.0  # módulo de corredor (comprimento x largura interior)
N_MODULES = 3
TWIN = 6.0  # sala do gémeo TWIN x TWIN
EYE = 1.6  # centro dos quadros (altura dos olhos)
FRAME_B, FRAME_D = 0.08, 0.05  # largura e profundidade da moldura
# Área interior (fotografia) de cada variante; outras proporções usam letterbox no Unity.
VARIANTS = {"Landscape": (1.2, 0.9), "Portrait": (0.9, 1.2), "Square": (1.0, 1.0)}
# IDs fixos dos dispositivos (contracts/v1.md, iot/simulator.py).
DEVICES = {
    "Twin_Sensor": "00000000-0000-4000-8000-0000000000a1",
    "Twin_Light": "00000000-0000-4000-8000-0000000000a2",
    "Twin_Fan": "00000000-0000-4000-8000-0000000000a3",
}


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
        o.parent = parent
    return o


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


def sign(name, body, loc, face, coll, mat, size=0.3):
    """Texto em relevo (mesh, para ir no FBX) numa parede. face: direção para onde o texto olha ('-y', '+x', '-x')."""
    cu = bpy.data.curves.new(name, "FONT")
    cu.body, cu.size, cu.align_x, cu.align_y, cu.extrude = body, size, "CENTER", "CENTER", 0.01
    cu.resolution_u = 3  # curvas das letras: 12 por omissão era a maior parte dos vértices da cena (T035)
    tmp = bpy.data.objects.new(name, cu)
    bpy.context.scene.collection.objects.link(tmp)
    bpy.context.view_layer.update()
    me = bpy.data.meshes.new_from_object(tmp.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    bpy.data.objects.remove(tmp)
    bpy.data.curves.remove(cu)
    rot_z = {"-y": 0, "+x": 90, "-x": -90}[face]
    me.transform(Matrix.Rotation(math.radians(rot_z), 4, "Z") @ Matrix.Rotation(math.radians(90), 4, "X"))
    me.name = name
    box_uv(me)
    return obj(name, me, coll, loc=loc, mat=mat)


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
    o = obj(f"Label_{body}", cu, coll, loc=(loc[0], loc[1], 0.02), mat=mat)
    o.rotation_euler = (0, 0, math.radians(90))  # legível na planta com a entrada à esquerda
    return o


def build():
    cols = reset()
    mats = {
        "wall": material("Wall", (0.85, 0.84, 0.80), tex=plaster_texture()),
        "floor": material("Floor", (0.45, 0.33, 0.22), tex=wood_texture()),
        "ceiling": material("Ceiling", (0.95, 0.95, 0.95)),
        "frame": material("FrameWood", (0.18, 0.12, 0.08)),
        "photo": material("PhotoPlaceholder", (0.55, 0.6, 0.65)),
        "twin": material("TwinDevice", (0.2, 0.45, 0.7), rough=0.4),
        "label": material("Label", (0.8, 0.1, 0.1)),
        "skirting": material("Skirting", (0.22, 0.22, 0.24), rough=0.5),
        "runner": material("Runner", (0.42, 0.1, 0.12), rough=0.9),
        "lamp": material("LampEmit", (1.0, 0.95, 0.82), rough=0.3, emit=4.0),
        "metal": material("Metal", (0.62, 0.63, 0.65), rough=0.3, metal=1.0),
        "sign": material("Sign", (0.12, 0.12, 0.13), rough=0.4),
        "plaque": material("Plaque", (0.93, 0.91, 0.86), rough=0.6),
        "screen": material("ScreenEmit", (0.25, 0.55, 0.9), rough=0.2, emit=2.0),
        "pot": material("Pot", (0.62, 0.36, 0.24)),
        "plant": material("Plant", (0.16, 0.38, 0.17), rough=0.8),
    }
    sk_h, sk_t = 0.12, 0.02  # rodapé: altura e espessura

    def skirting(name, segs, coll, parent=None, loc=(0, 0, 0)):
        """Rodapé: segs são retângulos (x0, x1, y0, y1) em planta, já encostados à face interior da parede."""
        return obj(name, mesh(name, [(*s, 0, sk_h) for s in segs]), coll, loc=loc, mat=mats["skirting"], parent=parent)
    arch, frames, props, twin, notes, tmpl = (cols[k] for k in
                                              ("Architecture", "Frames", "Props", "DigitalTwin", "Annotations", "_Templates"))

    templates = {}
    for i, (name, (w, h)) in enumerate(VARIANTS.items()):
        templates[name] = build_frame_template(name, w, h, tmpl, mats)
        templates[name].location = (HALL + 4, 2 + 2 * i, EYE)  # prateleira fora do museu

    # Entrada: y 0..HALL, porta na frente, passagem para o corredor ao fundo.
    hx = HALL / 2
    obj("Hall_Floor", mesh("Hall_Floor", [(-hx, hx, 0, HALL, -0.1, 0)]), arch, mat=mats["floor"])
    obj("Hall_Ceiling", mesh("Hall_Ceiling", [(-hx, hx, 0, HALL, H, H + 0.1)]), arch, mat=mats["ceiling"])
    obj("Hall_Walls", mesh("Hall_Walls", [
        *wall_with_gap(0, -hx - T / 2, hx + T / 2, DOOR_W, DOOR_H),
        *wall_with_gap(HALL, -hx - T / 2, hx + T / 2, MOD_W, H - 0.5),  # lintel marca a entrada nas exposições
        wall_x(-hx, 0, HALL), wall_x(hx, 0, HALL),
    ]), arch, mat=mats["wall"])
    ix, g = hx - T / 2, MOD_W / 2 + T / 2  # face interior das paredes laterais; fim das paredes do corredor
    skirting("Hall_Skirting", [
        (-ix, -DOOR_W / 2 - 0.1, T / 2, T / 2 + sk_t), (DOOR_W / 2 + 0.1, ix, T / 2, T / 2 + sk_t),
        (-ix, -g, HALL - T / 2 - sk_t, HALL - T / 2), (g, ix, HALL - T / 2 - sk_t, HALL - T / 2),
        (-ix, -ix + sk_t, T / 2, HALL - T / 2), (ix - sk_t, ix, T / 2, HALL - T / 2),
    ], arch)
    d = DOOR_W / 2
    obj("Hall_DoorFrame", mesh("Hall_DoorFrame", [  # aro da porta, saliente dos dois lados da parede
        (-d - 0.1, -d, -0.15, 0.15, 0, DOOR_H + 0.1), (d, d + 0.1, -0.15, 0.15, 0, DOOR_H + 0.1),
        (-d - 0.1, d + 0.1, -0.15, 0.15, DOOR_H, DOOR_H + 0.1),
    ]), arch, mat=mats["frame"])
    obj("Hall_CeilingLights", mesh("Hall_CeilingLights", [
        cyl(x, y, H - 0.04, H, 0.25, n=24) for x in (-2, 2) for y in (2, 6)
    ]), arch, mat=mats["lamp"])
    sign("Sign_Title", "Museu Virtual", (-ix + 0.015, HALL / 2, 2.3), "+x", props, mats["sign"], size=0.45)
    sign("Sign_Exhibitions", "Exposições", (0, HALL - T / 2 - 0.015, H - 0.25), "-y", props, mats["sign"])
    obj("Props_Bench", mesh("Props_Bench", [
        (-1.0, 1.0, HALL / 2 - 0.2, HALL / 2 + 0.2, 0.38, 0.45),  # assento
        (-0.9, -0.8, HALL / 2 - 0.15, HALL / 2 + 0.15, 0, 0.38), (0.8, 0.9, HALL / 2 - 0.15, HALL / 2 + 0.15, 0, 0.38),
    ]), props, mat=mats["frame"])
    obj("Props_Reception", mesh("Props_Reception", [
        (1.8, 3.4, 1.6, 2.1, 0, 1.0), (1.75, 3.45, 1.5, 2.15, 1.0, 1.05),  # balcão + tampo saliente
    ]), props, mat=mats["frame"])
    for side, x in (("L", -ix + 0.45), ("R", ix - 0.45)):
        pot = obj(f"Props_Plant_{side}", mesh(f"Props_Plant_{side}", [cyl(x, HALL - 0.7, 0, 0.45, 0.2, 0.24)]),
                  props, mat=mats["pot"])
        obj(f"Props_Plant_{side}_Leaves", mesh(f"Props_Plant_{side}_Leaves", [cyl(x, HALL - 0.7, 0.45, 1.7, 0.32, 0.02, n=8)]),
            props, mat=mats["plant"], parent=pot)

    # Corredor modular: o módulo começa em y=0 local e acaba em y=MOD_L, por isso encaixa sem folgas.
    mx = MOD_W / 2
    module_mesh = mesh("CorridorModule", [
        (-mx - T / 2, mx + T / 2, 0, MOD_L, -0.1, 0),
        wall_x(-mx, 0, MOD_L), wall_x(mx, 0, MOD_L),
    ])
    ceiling_mesh = mesh("CorridorModule_Ceiling", [(-mx - T / 2, mx + T / 2, 0, MOD_L, H, H + 0.1)])
    module_mesh.materials.append(mats["wall"])
    module_mesh.materials.append(mats["floor"])
    ceiling_mesh.materials.append(mats["ceiling"])
    for poly in module_mesh.polygons:  # chão do módulo a castanho, paredes a branco
        poly.material_index = 1 if poly.normal.z > 0.5 and poly.center.z < 0.01 else 0
    order = list(VARIANTS)
    for k in range(N_MODULES):
        tag = f"M{k + 1:02d}"
        m = obj(f"CorridorModule_{k + 1:02d}", module_mesh if k == 0 else module_mesh.copy(), arch,
                loc=(0, HALL + k * MOD_L, 0))
        obj(f"{tag}_Ceiling", ceiling_mesh if k == 0 else ceiling_mesh.copy(), arch, parent=m)
        # Detalhes do módulo (filhos, para irem no corridor_module.fbx); meshes próprias por causa do FBX.
        wx = mx - T / 2
        skirting(f"{tag}_Skirting", [(-wx, -wx + sk_t, 0, MOD_L), (wx - sk_t, wx, 0, MOD_L)], arch, parent=m)
        obj(f"{tag}_Runner", mesh(f"{tag}_Runner", [(-0.8, 0.8, 0, MOD_L, 0, 0.008)]), arch, mat=mats["runner"], parent=m)
        obj(f"{tag}_CeilingLight", mesh(f"{tag}_CeilingLight", [(-0.12, 0.12, 0.6, MOD_L - 0.6, H - 0.04, H)]),
            arch, mat=mats["lamp"], parent=m)
        for side, x, rot in (("L", -mx + T / 2 + FRAME_D / 2, 90), ("R", mx - T / 2 - FRAME_D / 2, -90)):
            slot = obj(f"{tag}_Slot_{side}", None, frames, loc=(x, MOD_L / 2, EYE), parent=m)
            slot.empty_display_type, slot.empty_display_size = "ARROWS", 0.3
            slot.rotation_euler = (0, 0, math.radians(rot))  # -Y da moldura aponta para o centro do corredor
            slot["slot"] = f"{tag}_{side}"
            place_frame(templates[order[(2 * k + (side == "R")) % 3]], slot, frames, tag)
            # Em coordenadas do slot: X ao longo da parede, -Y para o corredor, parede em y=+FRAME_D/2.
            w = FRAME_D / 2
            obj(f"{tag}_PictureLight_{side}", mesh(f"{tag}_PictureLight_{side}", [
                (-0.3, 0.3, -0.16, -0.1, 0.78, 0.83),  # barra de luz
                (-0.2, -0.17, -0.1, w, 0.8, 0.82), (0.17, 0.2, -0.1, w, 0.8, 0.82),  # braços até à parede
            ], cull=False), frames, mat=mats["metal"], parent=slot)
            obj(f"{tag}_Plaque_{side}", mesh(f"{tag}_Plaque_{side}", [(0.78, 1.0, w - 0.012, w, -0.4, -0.26)], cull=False),
                frames, mat=mats["plaque"], parent=slot)

    # Sala do gémeo digital: estado da exposição física (luz, ventoinha, sensor, moldura real).
    y0 = HALL + N_MODULES * MOD_L
    tx = TWIN / 2
    obj("Twin_Floor", mesh("Twin_Floor", [(-tx, tx, y0, y0 + TWIN, -0.1, 0)]), arch, mat=mats["floor"])
    obj("Twin_Ceiling", mesh("Twin_Ceiling", [(-tx, tx, y0, y0 + TWIN, H, H + 0.1)]), arch, mat=mats["ceiling"])
    obj("Twin_Walls", mesh("Twin_Walls", [
        *wall_with_gap(y0, -tx - T / 2, tx + T / 2, MOD_W, H - 0.5),
        wall_y(y0 + TWIN, -tx - T / 2, tx + T / 2),
        wall_x(-tx, y0, y0 + TWIN), wall_x(tx, y0, y0 + TWIN),
    ]), arch, mat=mats["wall"])
    iw, back = tx - T / 2, y0 + TWIN - T / 2  # faces interiores: paredes laterais e parede do fundo
    skirting("Twin_Skirting", [
        (-iw, -g, y0 + T / 2, y0 + T / 2 + sk_t), (g, iw, y0 + T / 2, y0 + T / 2 + sk_t),
        (-iw, iw, back - sk_t, back),
        (-iw, -iw + sk_t, y0 + T / 2, back), (iw - sk_t, iw, y0 + T / 2, back),
    ], arch)
    sign("Sign_Twin", "Gémeo digital", (0, y0 - T / 2 - 0.015, H - 0.25), "-y", props, mats["sign"])
    cy = y0 + TWIN / 2
    obj("Twin_Pedestal", mesh("Twin_Pedestal", [(-0.3, 0.3, cy - 0.3, cy + 0.3, 0, 1.0)]), twin, mat=mats["wall"])
    # Objetos separados e com nome fixo: o Unity liga cada um ao dispositivo pelo nome ou pelo device_id.
    devices = {
        "Twin_Light": [cyl(0, cy, H - 0.45, H, 0.015),                       # haste
                       cyl(0, cy, H - 0.65, H - 0.45, 0.28, 0.08, n=24)],     # abajur
        "Twin_Fan": [cyl(0, cy, 1.0, 1.04, 0.12, n=24),                       # base no pedestal
                     cyl(0, cy, 1.04, 1.32, 0.02)],                           # coluna
        "Twin_Sensor": [(iw - 0.05, iw, cy + 1.5, cy + 1.62, 1.4, 1.52)],
    }
    for name, parts in devices.items():
        o = obj(name, mesh(name, parts), twin, mat=mats["twin"])
        o["device_id"] = DEVICES[name]
    # Rotor separado e com pivô no eixo: o Unity roda-o em torno do seu eixo local quando a ventoinha liga.
    obj("Twin_Fan_Rotor", mesh("Twin_Fan_Rotor", [
        cyl(0, 1.45, cy - 0.04, cy + 0.04, 0.17, n=24, axis="y"),  # grelha, virada para a entrada
        cyl(0, 1.45, cy - 0.07, cy - 0.04, 0.04, axis="y"),        # cubo
    ]), twin, mat=mats["twin"], parent=bpy.data.objects["Twin_Fan"])
    obj("Twin_Light_Bulb", mesh("Twin_Light_Bulb", [cyl(0, cy, H - 0.67, H - 0.65, 0.22, n=24)]),
        twin, mat=mats["lamp"], parent=bpy.data.objects["Twin_Light"])
    obj("Twin_VentGrille", mesh("Twin_VentGrille", [
        (iw - 0.03, iw, cy - 0.45, cy + 0.45, 2.3, 2.34), (iw - 0.03, iw, cy - 0.45, cy + 0.45, 2.76, 2.8),
        (iw - 0.03, iw, cy - 0.45, cy - 0.41, 2.34, 2.76), (iw - 0.03, iw, cy + 0.41, cy + 0.45, 2.34, 2.76),
        *[(iw - 0.05, iw, cy - 0.41, cy + 0.41, z, z + 0.02) for z in (2.38, 2.46, 2.54, 2.62, 2.7)],  # lâminas
    ]), twin, mat=mats["metal"])
    tyy = y0 + 1.3  # terminal de controlo à entrada da sala, virado para quem entra
    terminal = obj("Twin_Terminal", mesh("Twin_Terminal", [
        (-2.45, -1.95, tyy - 0.2, tyy + 0.2, 0, 0.04),        # base
        (-2.23, -2.17, tyy - 0.03, tyy + 0.03, 0.04, 1.0),    # coluna
        (-2.5, -1.9, tyy - 0.04, tyy + 0.04, 1.0, 1.4),       # caixa do ecrã
    ]), twin, mat=mats["metal"])
    obj("Twin_Terminal_Screen", mesh("Twin_Terminal_Screen", [(-2.46, -1.94, tyy - 0.05, tyy - 0.04, 1.04, 1.36)]),
        twin, mat=mats["screen"], parent=terminal)
    # Três molduras da exposição física na parede do fundo.
    for i, (variant, x) in enumerate((("Portrait", -1.9), ("Landscape", 0.0), ("Square", 1.9)), 1):
        phys = obj(f"Twin_PhysicalFrame_{i}", None, twin, loc=(x, back - FRAME_D / 2, EYE))
        phys.empty_display_type = "ARROWS"
        place_frame(templates[variant], phys, twin, f"Twin{i}")

    # Anotações: só para a planta e para validar a escala; não vão para o FBX.
    text("Entrada", (0, HALL / 2 + 1.5), notes, mats["label"])
    text("Corredor modular", (0, HALL + N_MODULES * MOD_L / 2), notes, mats["label"])
    text("Gémeo digital", (1.8, y0 + TWIN / 2), notes, mats["label"])
    obj("Visitor_1m75", mesh("Visitor_1m75", [(-0.25, 0.25, -0.15, 0.15, 0, 1.75)]), notes,
        loc=(-1.5, 2.0, 0), mat=mats["label"])

    # Pivôs úteis (T033): pousados pela base, candeeiro pelo ponto de fixação no teto, rotor no eixo.
    for name, where in (("Props_Bench", "base"), ("Props_Reception", "base"), ("Props_Plant_L", "base"),
                        ("Props_Plant_R", "base"), ("Hall_DoorFrame", "base"), ("Twin_Pedestal", "base"),
                        ("Twin_Fan_Rotor", "center"), ("Twin_Fan", "base"), ("Twin_Light", "top"),
                        ("Twin_Sensor", "center"), ("Twin_VentGrille", "center"), ("Twin_Terminal", "base")):
        set_origin(bpy.data.objects[name], where)
    return cols, y0 + TWIN


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

def render(cam_data, loc, rot, path, res, hide):
    s = bpy.context.scene
    cam = bpy.data.objects.new("Cam", cam_data)
    s.collection.objects.link(cam)
    cam.location, cam.rotation_euler = loc, rot
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
    """T033: escala/rotação aplicadas e malhas limpas (sem faces degeneradas, duplicadas ou com normais trocadas)."""
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
            for k in ("device_id", "aspect", "slot"):
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
    cols, length = build()

    # Planta: câmara ortográfica de cima, rodada para o percurso ficar na horizontal.
    plan = bpy.data.cameras.new("Plan")
    plan.type, plan.ortho_scale = "ORTHO", length + 1.0
    plan.clip_start = 30 - 2.6  # corte horizontal a 2,6 m, como numa planta: lintéis e tetos não tapam as passagens
    render(plan, (0, length / 2, 30), (0, 0, math.radians(90)), DOCS / "planta.jpg", (2200, 800),
           hide=lambda o: "Ceiling" in o.name or in_coll(o, "_Templates"))
    # Vista do visitante à entrada, a olhar para o corredor.
    view = bpy.data.cameras.new("View")
    view.lens = 18
    render(view, (0, 1.0, EYE), (math.radians(90), 0, 0), DOCS / "blockout.jpg", (1600, 900),
           hide=lambda o: in_coll(o, "Annotations", "_Templates"))
    twin_view = bpy.data.cameras.new("TwinView")
    twin_view.lens = 16
    render(twin_view, (1.2, length - TWIN + 0.6, EYE), (math.radians(90), 0, math.radians(8)), DOCS / "gemeo.jpg",
           (1600, 900), hide=lambda o: in_coll(o, "Annotations", "_Templates"))

    museum = [o for o in bpy.data.objects if not in_coll(o, "Annotations", "_Templates")]
    errors = check_meshes(museum)
    errors += export(EXPORT / "museum_blockout.fbx", museum)
    module = bpy.data.objects["CorridorModule_01"]
    errors += export(EXPORT / "corridor_module.fbx", tree(module), zero=module)
    for name in VARIANTS:
        t = bpy.data.objects[f"Frame_{name}"]
        errors += export(EXPORT / f"frame_{name.lower()}.fbx", tree(t), zero=t)
    if errors:
        raise RuntimeError("verificação falhou:\n" + "\n".join(errors))

    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND))
    verts = sum(len(o.data.vertices) for o in museum if o.type == "MESH")
    tris = sum(len(p.vertices) - 2 for o in museum if o.type == "MESH" for p in o.data.polygons)
    print(f"ok: {len(museum)} objetos exportados, {verts} vértices, {tris} triângulos; meshes e FBX verificados; "
          f"comprimento {length:.1f} m; gravado {BLEND.name}; FBX em {EXPORT.name}/")


main()
