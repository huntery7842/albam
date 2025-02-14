from enum import Enum
import io
from pathlib import PureWindowsPath

import bpy
from kaitaistruct import KaitaiStream

from albam.lib.blender import get_bl_teximage_nodes
from albam.lib.dds import DDSHeader
from albam.registry import blender_registry
from albam.vfs import VirtualFile
from .structs.tex_112 import Tex112
from .structs.tex_157 import Tex157


class TextureType2(Enum):  # TODO: unify
    # TODO: complete
    DIFFUSE = 20
    SPECULAR = 25
    NORMAL = 31


class TextureType(Enum):  # TODO: TextureTypeSlot
    DIFFUSE = 1
    NORMAL = 2
    SPECULAR = 3
    LIGHTMAP = 4
    UNK_01 = 5
    ALPHAMAP = 6
    ENVMAP = 7
    NORMAL_DETAIL = 8


NODE_NAMES_TO_TYPES = {
    'Diffuse BM': TextureType.DIFFUSE,
    'Normal NM': TextureType.NORMAL,
    'Specular MM': TextureType.SPECULAR,
    'Lightmap LM': TextureType.LIGHTMAP,
    'Alpha Mask AM': TextureType.ALPHAMAP,
    'Environment CM': TextureType.ENVMAP,
    'Detail DNM': TextureType.NORMAL_DETAIL
}

NODE_NAMES_TO_TYPES_2 = {  # TODO: unify
    'Diffuse BM': TextureType2.DIFFUSE,
    'Normal NM': TextureType2.NORMAL,
    'Specular MM': TextureType2.SPECULAR,
    'Detail DNM': TextureType2.NORMAL
}


TEX_FORMAT_MAPPER = {
    2: b"DXT1",  # FIXME: unchecked
    14: b"",  # uncompressed
    19: b"DXT1",
    20: b"DXT1",  # BM/Diffuse
    23: b"DXT5",
    24: b"DXT5",
    24: b"DXT5",  # BM/Diffuse (UI?)
    25: b"DXT1",  # MM/Specular
    31: b"DXT5",  # NM/Normal
    32: b"DXT5",
    35: b"DXT5",
    39: b"",  # uncompressed
    40: b"",  # uncompressed
    43: b"DXT1",  # FIXME: unchecked
    "DXT1": b"DXT1",
    "DXT5": b"DXT5",
}

# FIXME: take into account type of texture (BM/NM/MM, etc.)
DDS_FORMAT_MAP = {
    b"DXT1": 20,
    b"DXT5": 31,
}

APPID_SERIALIZE_MAPPER = {
    "re0": lambda: _serialize_texture_21,
    "re1": lambda: _serialize_texture_21,
    "re5": lambda: _serialize_texture_156,
    "rev1": lambda: _serialize_texture_21,
    "rev2": lambda: _serialize_texture_21,
}

APPID_TEXCLS_MAP = {
    "re0": Tex157,
    "re1": Tex157,
    "rev1": Tex157,
    "rev2": Tex157,
    "re5": Tex112,
}


TEX_TYPE_MAPPER = {
    0xcd06f: TextureType.DIFFUSE,
    0x22660: TextureType.NORMAL,
    0xaa6f0: TextureType.LIGHTMAP,
    0xed1b: TextureType.SPECULAR,
    0x75a53: TextureType.NORMAL_DETAIL,
    0x64c43: TextureType.ENVMAP,
    0x1698a: TextureType.ALPHAMAP,  # tTransparencyMap
    # 0xff5be: TextureType.UNK_01, # tAlbedoBlendMap
    # 0x1cb2a: TextureType.UNK_01, # ttHairShiftMap
    # 0xed93b: TextureType.UNK_01, # tEmissionMap
    # 0xa9787: TextureType.UNK_01, # tShininessMap
    # 0x39c0:  TextureType.UNK_01, # tVtxDispMask
    # 0x4934a: TextureType.UNK_01, # tVtxDisplacement
    # 0xed6be: TextureType.UNK_01, # tNormalBlendMap
    # 0x1e421: TextureType.UNK_01, # tOcclusionMap
    # 0x343f4: TextureType.UNK_01, # tSphereMap
    # 0x57C1C: TextureType.UNK_01, # not in rev2 mxt
    # 0x6ab7e: TextureType.UNK_01, # tIndirectMap
    # 0x181cf: TextureType.UNK_01, # tSpecularBlendMap
    # 0xd4694: TextureType.UNK_01, # tDetailNormalMap2
    # 0x7b571: TextureType.UNK_01, # tHeightMap
    # 0x5f2a:  TextureType.UNK_01, # tThinMap
    # 0xc3df7: TextureType.UNK_01, # not in re6 mxt
    # 0x88165: TextureType.UNK_01, # tDetailMaskMap
    # 0x7e9aa: TextureType.UNK_01, # not in re6 mxt
    # 0x62fde: TextureType.UNK_01, # not in re6 mxt
    # 0x52e1:  TextureType.UNK_01, # not in re6 mxt

}


def build_blender_textures(app_id, mod_file_item, context, parsed_mod, mrl=None):
    textures = [None]  # materials refer to textures in index-1

    file_list = context.scene.albam.file_explorer.file_list

    src_textures = getattr(parsed_mod.materials_data, "textures", None) or getattr(mrl, "textures", None)
    if not src_textures:
        return textures
    TexCls = APPID_TEXCLS_MAP[app_id]

    for i, texture_slot in enumerate(src_textures):
        # FIXME: use VirtualFile and commit late
        texture_path = getattr(texture_slot, "texture_path", None) or texture_slot
        new_texture_path = (
            mod_file_item.tree_node.root_id + "::" + texture_path.replace("\\", "::") + ".tex"
        )
        try:
            texture_item = file_list[new_texture_path]
            tex_bytes = texture_item.get_bytes()
        except KeyError:
            tex_bytes = None

        if not tex_bytes:
            print(f"texture_path {texture_path} not found in arc")
            textures.append(None)
            # TODO: handle missing texture
            continue
        tex = TexCls.from_bytes(tex_bytes)
        tex._read()
        try:
            compression_fmt = TEX_FORMAT_MAPPER[tex.compression_format]
            dds_header = DDSHeader(
                dwHeight=tex.height,
                dwWidth=tex.width,
                pixelfmt_dwFourCC=compression_fmt,
                dwMipMapCount=tex.num_mipmaps_per_image // tex.num_images,
            )
            dds_header.set_constants()
            dds_header.set_variables(compressed=bool(compression_fmt), cubemap=tex.num_images > 1)
            dds = bytes(dds_header) + tex.dds_data
        except Exception as err:
            # TODO: log this instead of printing it
            print(f'Error converting "{texture_path}" to dds: {err}')
            textures.append(None)
            continue

        # XXX Revisit
        app_id = mod_file_item.app_id
        tex_name = PureWindowsPath(texture_path).name
        bl_image = bpy.data.images.new(f"{tex_name}.dds", tex.width, tex.height)
        bl_image.source = "FILE"
        bl_image.pack(data=dds, data_len=len(dds))

        bl_image.albam_asset.original_bytes = tex_bytes
        bl_image.albam_asset.app_id = app_id
        bl_image.albam_asset.relative_path = texture_path + ".tex"
        bl_image.albam_asset.extension = "tex"

        custom_properties = bl_image.albam_custom_properties.get_appid_custom_properties(app_id)
        custom_properties.set_from_source(tex)

        textures.append(bl_image)

    return textures


def assign_textures(mtfw_material, bl_material, textures, from_mrl=False):
    for texture_type in TextureType:
        tex_index = _find_texture_index(mtfw_material, texture_type, from_mrl)
        if tex_index == 0:
            continue
        try:
            texture_target = textures[tex_index]
        except IndexError:
            print(f"tex_index {tex_index} not found. Texture len(): {len(textures)}")
            continue
        if texture_target is None:
            # This means the conversion failed before
            continue
        if texture_type.value == 6:
            print("texture_type not supported", texture_type)
            continue
        texture_node = bl_material.node_tree.nodes.new("ShaderNodeTexImage")
        texture_code_to_blender_texture(texture_type.value, texture_node, bl_material)
        texture_node.image = texture_target
        # change color settings for normal and detail maps
        if texture_type.value == 2 or texture_type.value == 8:
            texture_node.image.colorspace_settings.name = "Non-Color"


def _find_texture_index(mtfw_material, texture_type, from_mrl=False):
    tex_index = 0

    if from_mrl is False:
        tex_index = mtfw_material.texture_slots[texture_type.value - 1]
    else:
        for resource in mtfw_material.resources:
            try:
                shader_object_id = resource.shader_object_id.value
            except AttributeError:
                # TODO: report as warnings, this means the enum doesn't exit for this app
                shader_object_id = resource.shader_object_id

            if TEX_TYPE_MAPPER.get((shader_object_id >> 12)) == texture_type:
                tex_index = resource.value_cmd.tex_idx
                break
    return tex_index


def texture_code_to_blender_texture(texture_code, blender_texture_node, blender_material):
    """
    Function for detecting texture type and map it to blender shader sockets
    texture_code : index for detecting type of a texture
    blender_texture_node : image texture node
    blender_material : shader material
    """
    # blender_texture_node.use_map_alpha = True
    shader_node_grp = blender_material.node_tree.nodes.get("MTFrameworkGroup")
    link = blender_material.node_tree.links.new

    if texture_code == 1:
        # Diffuse _BM
        link(blender_texture_node.outputs["Color"], shader_node_grp.inputs[0])
        link(blender_texture_node.outputs["Alpha"], shader_node_grp.inputs[1])
        blender_texture_node.location = (-300, 350)
        # blender_texture_node.use_map_color_diffuse = True
    elif texture_code == 2:
        # Normal _NM
        blender_texture_node.location = (-300, 0)
        link(blender_texture_node.outputs["Color"], shader_node_grp.inputs[2])
        link(blender_texture_node.outputs["Alpha"], shader_node_grp.inputs[3])

    elif texture_code == 3:
        # Specular _MM
        blender_texture_node.location = (-300, -350)
        link(blender_texture_node.outputs["Color"], shader_node_grp.inputs[4])

    elif texture_code == 4:
        # Lightmap _LM
        blender_texture_node.location = (-300, -700)
        uv_map_node = blender_material.node_tree.nodes.new("ShaderNodeUVMap")
        uv_map_node.location = (-500, -700)
        uv_map_node.uv_map = "uv2"
        link(uv_map_node.outputs[0], blender_texture_node.inputs[0])
        link(blender_texture_node.outputs["Color"], shader_node_grp.inputs[5])
        shader_node_grp.inputs[6].default_value = 1

    elif texture_code == 5:
        # Lightmap with Alpha mask in Re5
        blender_texture_node.location = (-300, -1050)

    elif texture_code == 6:
        # Alpha mask _AM
        blender_texture_node.location = (-300, -1400)
        link(blender_texture_node.outputs["Color"], shader_node_grp.inputs[7])
        shader_node_grp.inputs[8].default_value = 1

    #  elif texture_code == 7:
    #    # Enviroment _CM
    #    blender_texture_node.location = (-800, -350)
    #    link(blender_texture_node.outputs['Color'], shader_node_grp.inputs[9])

    elif texture_code == 8:
        # Detail normal map
        blender_texture_node.location = (-300, -1750)
        tex_coord_node = blender_material.node_tree.nodes.new("ShaderNodeTexCoord")
        tex_coord_node.location = (-700, -1750)
        mapping_node = blender_material.node_tree.nodes.new("ShaderNodeMapping")
        mapping_node.location = (-500, -1750)

        link(tex_coord_node.outputs[2], mapping_node.inputs[0])
        link(mapping_node.outputs[0], blender_texture_node.inputs[0])
        link(blender_texture_node.outputs["Color"], shader_node_grp.inputs[10])
        link(blender_texture_node.outputs["Alpha"], shader_node_grp.inputs[11])

        shader_node_grp.inputs[12].default_value = 1
        # TODO move it to function
        # Link the material properites value
        for x in range(3):
            d = mapping_node.inputs[3].driver_add("default_value", x)
            var1 = d.driver.variables.new()
            var1.name = "detail_multiplier"
            var1.targets[0].id_type = "MATERIAL"
            var1.targets[0].id = blender_material
            var1.targets[0].data_path = '["unk_detail_factor"]'
            d.driver.expression = var1.name
    else:
        print("texture_code not supported", texture_code)
        # TODO: 7 CM cubemap


def serialize_textures(app_id, bl_materials):
    # XXX Only works with `MT Framework shader`, and no checks performed yet
    exported_textures = get_bl_teximage_nodes(bl_materials)
    serialize_func = APPID_SERIALIZE_MAPPER[app_id]()

    bad_appid = []
    for im_name, data in exported_textures.items():
        if data["image"].albam_asset.app_id != app_id:
            bad_appid.append((im_name, data["image"].albam_asset.app_id))
    if bad_appid:
        raise AttributeError(
            f"The following images have an incorrect app_id (needs: {app_id}): {bad_appid}\n"
            "Go to Image -> tools -> Albam and select the proper app_id for each."
        )

    for dict_tex in exported_textures.values():
        vfile = serialize_func(app_id, dict_tex)
        dict_tex["serialized_vfile"] = vfile

    return exported_textures


def _serialize_texture_156(app_id, dict_tex):
    bl_im = dict_tex["image"]
    dds_header = DDSHeader.from_bl_image(bl_im)

    tex = Tex112()
    tex.id_magic = b"TEX\x00"
    tex.version = 112
    tex.revision = 34  # FIXME: not really, changes with cubemaps
    tex.num_mipmaps_per_image = dds_header.dwMipMapCount
    tex.num_images = dds_header.image_count
    tex.width = bl_im.size[0]
    tex.height = bl_im.size[1] // dds_header.image_count  # cubemaps are a vertical strip in Blender
    tex.reserved = 0
    tex.compression_format = dds_header.pixelfmt_dwFourCC.decode()

    tex.cube_faces = [] if dds_header.image_count == 1 else _calculate_cube_faces_data(tex)
    tex.mipmap_offsets = dds_header.calculate_mimpap_offsets(tex.size_before_data_)
    tex.dds_data = dds_header.data

    custom_properties = bl_im.albam_custom_properties.get_appid_custom_properties(app_id)
    custom_properties.set_to_dest(tex)

    tex._check()

    final_size = tex.size_before_data_ + len(tex.dds_data)
    stream = KaitaiStream(io.BytesIO(bytearray(final_size)))
    tex._write(stream)
    relative_path = _handle_relative_path(bl_im)
    vf = VirtualFile(app_id, relative_path, data_bytes=stream.to_byte_array())
    return vf


def _serialize_texture_21(app_id, dict_tex):
    bl_im = dict_tex["image"]
    dds_header = DDSHeader.from_bl_image(bl_im)

    tex = Tex157()
    tex.id_magic = b"TEX\x00"
    tex_type = 0x209D  # TODO: enum
    reserved_01 = 0
    shift = 0
    constant = 1  # XXX Not really, see tests
    reserved_02 = 0
    dimension = 2 if not dds_header.is_proper_cubemap else 6

    custom_properties = bl_im.albam_custom_properties.get_appid_custom_properties(app_id)
    compression_format = custom_properties.compression_format or _infer_compression_format(dict_tex)

    packed_data_1 = (
        (tex_type & 0xffff) |
        ((reserved_01 & 0x00ff) << 16) |
        ((shift & 0x000f) << 24) |
        ((dimension & 0x000f) << 28)
    )

    width = bl_im.size[0]
    height = bl_im.size[1] // dds_header.image_count  # cubemaps are a vertical strip in Blender
    num_mipmaps = dds_header.dwMipMapCount
    packed_data_2 = (
        (num_mipmaps & 0x3f) |
        ((width & 0x1fff) << 6) |
        ((height & 0x1fff) << 19)
    )
    packed_data_3 = (
        (dds_header.image_count & 0xff) |
        ((compression_format & 0xff) << 8) |
        ((constant & 0x1fff) << 16) |
        ((reserved_02 & 0x003) << 29)
    )
    tex.packed_data_1 = packed_data_1
    tex.packed_data_2 = packed_data_2
    tex.packed_data_3 = packed_data_3
    tex.cube_faces = [] if dds_header.image_count == 1 else _calculate_cube_faces_data(tex)
    tex.mipmap_offsets = dds_header.calculate_mimpap_offsets(tex.size_before_data_)
    tex.dds_data = dds_header.data

    tex._check()
    final_size = tex.size_before_data_ + len(tex.dds_data)
    stream = KaitaiStream(io.BytesIO(bytearray(final_size)))
    tex._write(stream)
    relative_path = _handle_relative_path(bl_im)
    vf = VirtualFile(app_id, relative_path, data_bytes=stream.to_byte_array())
    return vf


def _infer_compression_format(dict_tex):
    """
    Infer the type of texture based on its usage in materials.
    E.g. if the bl_image is linked to a "BM" socket, it's diffuse.
    """
    # NOTE: this logic is duplicated in `_gather_tex_types`

    DEFAULT_COMPRESSION_FORMAT = TextureType2.DIFFUSE
    bl_im = dict_tex["image"]
    materials_dict = dict_tex["materials"]
    materials = [m[0] for m in materials_dict.values()]

    if not materials:
        # means texture is disconnected, could still happend
        # TODO: update then blender.lib function is updated
        return DEFAULT_COMPRESSION_FORMAT.value

    # Arbitrarily using the first material where the image is used to infer its type.
    # TODO: report discrepancies in texture usage (e.g. texture used both as Diffuse and Lightmap)
    bl_mat = materials[0]
    image_nodes = [node for node in bl_mat.node_tree.nodes if node.type == "TEX_IMAGE"]
    im_nodes = [node for node in image_nodes if node.image.name == bl_im.name]
    im_node = im_nodes[0] if im_nodes else None
    if not im_node:
        return DEFAULT_COMPRESSION_FORMAT.value
    links = im_node.outputs["Color"].links
    if not links:
        return DEFAULT_COMPRESSION_FORMAT.value
    mtfw_shader_link_name = links[0].to_socket.name
    try:
        tex_type = NODE_NAMES_TO_TYPES_2[mtfw_shader_link_name]
    except KeyError:
        print(f"Can\'t get correct compression_format for image '{bl_im.name}'."
              "Node '{mtfw_shader_link_name}' not supported yet. "
              "Using default {DEFAULT_COMPRESSION_FORMAT}. "
              "Set compression_format manually for now."
              )
        tex_type = DEFAULT_COMPRESSION_FORMAT

    return tex_type.value


def _handle_relative_path(bl_im):
    path = bl_im.albam_asset.relative_path or bl_im.name
    before, _, after = path.rpartition(".")
    if not before:
        path = f"{path}.tex"
    else:
        path = f"{before}.tex"
    return path


def _calculate_cube_faces_data(tex):
    # TODO: get real data
    # It seems having null data doesn't
    # affect the game much
    cube_faces = []
    for _ in range(3):
        cb = tex.CubeFace(_parent=tex, _root=tex._root)
        cb.field_00 = 0
        cb.negative_co = [0, 0, 0]
        cb.positive_co = [0, 0, 0]
        cb.uv = [0, 0]
        cube_faces.append(cb)
    return cube_faces


@blender_registry.register_custom_properties_image("tex_112", ("re5", ))
@blender_registry.register_blender_prop
class Tex112CustomProperties(bpy.types.PropertyGroup):
    unk_02: bpy.props.IntProperty(default=0)  # TODO u1
    unk_03: bpy.props.IntProperty(default=0)  # TODO u1
    red: bpy.props.FloatProperty(default=0.7)
    green: bpy.props.FloatProperty(default=0.7)
    blue: bpy.props.FloatProperty(default=0.7)
    alpha: bpy.props.FloatProperty(default=0.7)

    # XXX copy paste in mesh, material
    def set_from_source(self, mesh):
        # XXX assume only properties are part of annotations
        for attr_name in self.__annotations__:
            self.copy_attr(mesh, self, attr_name)

    def set_to_dest(self, mesh):
        for attr_name in self.__annotations__:
            self.copy_attr(self, mesh, attr_name)

    @staticmethod
    def copy_attr(src, dst, name):
        # will raise, making sure there's consistency
        src_value = getattr(src, name)
        setattr(dst, name, src_value)


@blender_registry.register_custom_properties_image("tex_157", ("re0", "re1", "rev1", "rev2"))
@blender_registry.register_blender_prop
class Tex157CustomProperties(bpy.types.PropertyGroup):
    compression_format: bpy.props.IntProperty(default=0, min=0, max=43)

    # XXX copy paste in mesh, material
    def set_from_source(self, mesh):
        # XXX assume only properties are part of annotations
        for attr_name in self.__annotations__:
            self.copy_attr(mesh, self, attr_name)

    def set_to_dest(self, mesh):
        for attr_name in self.__annotations__:
            self.copy_attr(self, mesh, attr_name)

    @staticmethod
    def copy_attr(src, dst, name):
        # will raise, making sure there's consistency
        src_value = getattr(src, name)
        setattr(dst, name, src_value)
