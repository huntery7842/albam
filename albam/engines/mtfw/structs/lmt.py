# This is a generated file! Please edit source .ksy file and use kaitai-struct-compiler to rebuild

import kaitaistruct
from kaitaistruct import KaitaiStruct, KaitaiStream, BytesIO


if getattr(kaitaistruct, 'API_VERSION', (0, 9)) < (0, 9):
    raise Exception("Incompatible Kaitai Struct Python API: 0.9 or later is required, but you have %s" % (kaitaistruct.__version__))

class Lmt(KaitaiStruct):
    def __init__(self, _io, _parent=None, _root=None):
        self._io = _io
        self._parent = _parent
        self._root = _root if _root else self
        self._read()

    def _read(self):
        self.id_magic = self._io.read_bytes(4)
        if not self.id_magic == b"\x4C\x4D\x54\x00":
            raise kaitaistruct.ValidationNotEqualError(b"\x4C\x4D\x54\x00", self.id_magic, self._io, u"/seq/0")
        self.version = self._io.read_u2le()
        self.num_block_offsets = self._io.read_u2le()
        self.block_offsets = []
        for i in range(self.num_block_offsets):
            self.block_offsets.append(Lmt.BlockOffset(self._io, self, self._root))


    class BlockOffset(KaitaiStruct):
        def __init__(self, _io, _parent=None, _root=None):
            self._io = _io
            self._parent = _parent
            self._root = _root if _root else self
            self._read()

        def _read(self):
            self.offset = self._io.read_u4le()

        @property
        def block_header(self):
            if hasattr(self, '_m_block_header'):
                return self._m_block_header

            _pos = self._io.pos()
            self._io.seek(self.offset)
            self._m_block_header = Lmt.BlockHeader(self._io, self, self._root)
            self._io.seek(_pos)
            return getattr(self, '_m_block_header', None)


    class BlockHeader(KaitaiStruct):
        def __init__(self, _io, _parent=None, _root=None):
            self._io = _io
            self._parent = _parent
            self._root = _root if _root else self
            self._read()

        def _read(self):
            self.ofs_frame = self._io.read_u4le()
            self.num_tracks = self._io.read_u4le()
            self.num_frames = self._io.read_u4le()
            self.unk_01 = []
            for i in range(25):
                self.unk_01.append(self._io.read_u4le())

            self.count_01 = self._io.read_u4le()
            self.ofs_buffer = self._io.read_u4le()
            self.unk_02 = []
            for i in range(16):
                self.unk_02.append(self._io.read_u4le())

            self.count_02 = self._io.read_u4le()
            self.ofs_02 = self._io.read_u4le()

        @property
        def tracks(self):
            if hasattr(self, '_m_tracks'):
                return self._m_tracks

            _pos = self._io.pos()
            self._io.seek(self.ofs_frame)
            self._m_tracks = []
            for i in range(self.num_tracks):
                self._m_tracks.append(Lmt.Track(self._io, self, self._root))

            self._io.seek(_pos)
            return getattr(self, '_m_tracks', None)


    class Track(KaitaiStruct):
        def __init__(self, _io, _parent=None, _root=None):
            self._io = _io
            self._parent = _parent
            self._root = _root if _root else self
            self._read()

        def _read(self):
            self.buffer_type = self._io.read_u1()
            self.usage = self._io.read_u1()
            self.joint_type = self._io.read_u1()
            self.bone_index = self._io.read_u1()
            self.unk_01 = self._io.read_f4le()
            self.len_data = self._io.read_u4le()
            self.ofs_data = self._io.read_u4le()
            self.unk_reference_data = []
            for i in range(4):
                self.unk_reference_data.append(self._io.read_f4le())


        @property
        def data(self):
            if hasattr(self, '_m_data'):
                return self._m_data

            _pos = self._io.pos()
            self._io.seek(self.ofs_data)
            self._m_data = self._io.read_bytes(self.len_data)
            self._io.seek(_pos)
            return getattr(self, '_m_data', None)



