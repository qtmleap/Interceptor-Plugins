"""Bundled plugin icons: path grammar, structural PNG/WebP validation and bounded safe file reads.

Standard library only and independent of repository_config (which wraps IconError in ToolError).
Validation is structural, as agreed with the native Core parser: bitstreams are never decoded, so passing
here does not prove an image decodes; the app renders a fallback when decoding fails.
"""
import base64
import binascii
import os
import re
import stat
import struct
import zlib

MAX_ICON_BYTES = 65_536
MAX_DIMENSION = 1_024
SUFFIXES = (".png", ".webp")
_PATH_PART = re.compile(r"[A-Za-z0-9._~-]+")
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_PNG_DEPTHS = {0: (1, 2, 4, 8, 16), 2: (8, 16), 3: (1, 2, 4, 8), 4: (8, 16), 6: (8, 16)}
_ICC_FLAG, _ALPHA_FLAG, _EXIF_FLAG, _XMP_FLAG = 0x20, 0x10, 0x08, 0x04


class IconError(Exception):
    pass


def valid_icon_path(value):
    """Source-path grammar (<=256 UTF-8 bytes, ASCII segments) plus a lowercase .png/.webp suffix."""
    return (isinstance(value, str) and value.isascii() and len(value) <= 256 and value.endswith(SUFFIXES)
            and all(_PATH_PART.fullmatch(part) and part not in (".", "..") for part in value.split("/")))


def _dimensions(width, height, what):
    if not (1 <= width <= MAX_DIMENSION and 1 <= height <= MAX_DIMENSION):
        raise IconError(f"{what} dimensions must each be 1...{MAX_DIMENSION}")
    return width, height


def validate_png(data):
    """Structural PNG check; returns (width, height)."""
    if data[:8] != _PNG_SIGNATURE:
        raise IconError("not a PNG file")
    offset, end = 8, len(data)
    ihdr = None
    seen_plte = seen_idat = idat_closed = seen_iend = False
    idat_bytes = 0
    first = True
    while offset < end:
        if seen_iend:
            raise IconError("PNG has data after IEND")
        if end - offset < 12:
            raise IconError("truncated PNG chunk")
        length, kind = struct.unpack(">I4s", data[offset:offset + 8])
        if length > 0x7FFFFFFF or offset + 12 + length > end:
            raise IconError("PNG chunk exceeds the file")
        if not re.fullmatch(rb"[A-Za-z]{2}[A-Z][A-Za-z]", kind):
            raise IconError("invalid PNG chunk type")
        body = data[offset + 8:offset + 8 + length]
        (crc,) = struct.unpack(">I", data[offset + 8 + length:offset + 12 + length])
        if zlib.crc32(kind + body) != crc:
            raise IconError("PNG chunk CRC mismatch")
        offset += 12 + length
        if first and kind != b"IHDR":
            raise IconError("PNG must start with IHDR")
        first = False
        if kind != b"IDAT" and seen_idat:
            idat_closed = True
        if kind == b"IHDR":
            if ihdr is not None or length != 13:
                raise IconError("invalid PNG IHDR")
            width, height, depth, color, compression, filtering, interlace = struct.unpack(">IIBBBBB", body)
            if color not in _PNG_DEPTHS or depth not in _PNG_DEPTHS[color] or compression or filtering or interlace > 1:
                raise IconError("unsupported PNG header")
            _dimensions(width, height, "PNG")
            ihdr = (width, height, depth, color)
        elif kind == b"PLTE":
            if seen_plte or seen_idat or ihdr[3] in (0, 4) or length % 3 or not 1 <= length // 3 <= 256 \
                    or length // 3 > 2 ** ihdr[2]:
                raise IconError("invalid PNG palette")
            seen_plte = True
        elif kind == b"IDAT":
            if idat_closed:
                raise IconError("PNG IDAT chunks are not contiguous")
            if ihdr[3] == 3 and not seen_plte:
                raise IconError("indexed PNG requires PLTE")
            seen_idat = True
            idat_bytes += length
        elif kind == b"IEND":
            if length:
                raise IconError("invalid PNG IEND")
            seen_iend = True
        elif kind in (b"acTL", b"fcTL", b"fdAT") or kind[0:1].isupper():
            raise IconError("animated or unknown critical PNG chunk")
    if ihdr is None or not seen_iend:
        raise IconError("PNG is missing IHDR or IEND")
    if not seen_idat or idat_bytes == 0:
        raise IconError("PNG has no image data")
    if ihdr[3] == 3 and not seen_plte:
        raise IconError("indexed PNG requires PLTE")
    return ihdr[0], ihdr[1]


def _vp8_dimensions(body):
    if len(body) < 10 or body[0] & 1 or body[3:6] != b"\x9d\x01\x2a":
        raise IconError("invalid WebP VP8 frame header")
    width, height = struct.unpack("<HH", body[6:10])
    if width >> 14 or height >> 14:
        raise IconError("WebP VP8 scaling is not supported")
    return width & 0x3FFF, height & 0x3FFF


def _vp8l_dimensions(body):
    if len(body) < 5 or body[0] != 0x2F or body[4] & 0xE0:
        raise IconError("invalid WebP VP8L header")
    (bits,) = struct.unpack("<I", body[1:5])
    return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1


def validate_webp(data):
    """Structural static WebP check; returns (width, height)."""
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        raise IconError("not a WebP file")
    if struct.unpack("<I", data[4:8])[0] != len(data) - 8:
        raise IconError("WebP RIFF size mismatch")
    offset, end = 12, len(data)
    index = 0
    flags = None
    canvas = None
    image = None  # (fourcc, width, height)
    seen = set()
    while offset < end:
        if end - offset < 8:
            raise IconError("truncated WebP chunk")
        fourcc = data[offset:offset + 4]
        (size,) = struct.unpack("<I", data[offset + 4:offset + 8])
        if not all(0x20 <= byte <= 0x7E for byte in fourcc):
            raise IconError("invalid WebP chunk FourCC")
        padded = size + (size & 1)
        if offset + 8 + padded > end:
            raise IconError("WebP chunk exceeds the file")
        body = data[offset + 8:offset + 8 + size]
        if size & 1 and data[offset + 8 + size] != 0:
            raise IconError("WebP chunk padding must be zero")
        offset += 8 + padded
        if fourcc in (b"ANIM", b"ANMF"):
            raise IconError("animated WebP is not supported")
        if fourcc == b"VP8X":
            if index != 0 or size != 10:
                raise IconError("invalid WebP VP8X")
            flags = body[0]
            if flags & 0xC3 or body[1:4] != b"\0\0\0":
                raise IconError("unsupported WebP VP8X flags")
            canvas = (int.from_bytes(body[4:7], "little") + 1, int.from_bytes(body[7:10], "little") + 1)
        elif fourcc in (b"VP8 ", b"VP8L"):
            if image is not None:
                raise IconError("WebP must contain exactly one image")
            width, height = (_vp8_dimensions if fourcc == b"VP8 " else _vp8l_dimensions)(body)
            image = (fourcc, *_dimensions(width, height, "WebP"))
        elif fourcc in (b"ICCP", b"ALPH", b"EXIF", b"XMP "):
            if fourcc in seen or flags is None:
                raise IconError(f"invalid WebP {fourcc.decode()} chunk")
            seen.add(fourcc)
            if fourcc == b"ICCP" and image is not None:
                raise IconError("WebP ICCP must precede the image")
            if fourcc == b"ALPH" and (image is not None or size < 1):
                raise IconError("invalid WebP ALPH chunk")
            if fourcc in (b"EXIF", b"XMP ") and image is None:
                raise IconError("WebP metadata must follow the image")
        index += 1
    if image is None:
        raise IconError("WebP has no image")
    _, width, height = image
    if b"ALPH" in seen and image[0] != b"VP8 ":
        raise IconError("WebP ALPH is only valid with VP8")
    if flags is not None:
        if canvas != (width, height):
            raise IconError("WebP canvas differs from the image")
        for flag, chunk in ((_ICC_FLAG, b"ICCP"), (_EXIF_FLAG, b"EXIF"), (_XMP_FLAG, b"XMP ")):
            if bool(flags & flag) != (chunk in seen):
                raise IconError("WebP metadata flags do not match its chunks")
        if b"ALPH" in seen and not flags & _ALPHA_FLAG:
            raise IconError("WebP ALPH requires the alpha flag")
    return width, height


def validate_icon_bytes(path, data):
    if not valid_icon_path(path):
        raise IconError("invalid icon path")
    if not 1 <= len(data) <= MAX_ICON_BYTES:
        raise IconError(f"icon must be 1...{MAX_ICON_BYTES} bytes")
    return (validate_png if path.endswith(".png") else validate_webp)(data)


def decode_asset(path, text):
    """Canonical standard base64 text -> validated icon bytes."""
    if not isinstance(text, str) or not text.isascii() or len(text) % 4 or len(text) > 4 * ((MAX_ICON_BYTES + 2) // 3):
        raise IconError("icon asset must be canonical base64")
    try:
        data = base64.b64decode(text, validate=True)
    except (ValueError, binascii.Error):
        raise IconError("icon asset must be canonical base64")
    if base64.b64encode(data).decode("ascii") != text:
        raise IconError("icon asset must be canonical base64")
    validate_icon_bytes(path, data)
    return data


def validate_package_assets(manifest, package, source_files):
    """Schema 2 package: `assets` is exactly {manifest.icon: base64}, and absent when there is no icon."""
    icon = manifest.get("icon")
    if icon is None:
        if "assets" in package:
            raise IconError("assets require manifest.icon")
        return
    assets = package.get("assets")
    if not isinstance(assets, dict) or set(assets) != {icon}:
        raise IconError("assets must contain exactly the manifest icon")
    if icon in source_files:
        raise IconError("icon path collides with a source file")
    decode_asset(icon, assets[icon])


def read_icon_file(plugin_directory, icon, *, repository_root=None):
    """Bounded regular-file read; an explicit trusted root permits system aliases above that root only."""
    if not valid_icon_path(icon):
        raise IconError("invalid icon path")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | os.O_NOFOLLOW
    parts = icon.split("/")
    fds = []
    try:
        try:
            if repository_root is None:
                anchor = os.path.sep
                directory_parts = os.path.abspath(plugin_directory).split(os.path.sep)
            else:
                # The caller selects the repository trust boundary. Resolve only that
                # boundary, then never resolve plugin or asset components below it.
                relative = os.path.relpath(os.path.abspath(plugin_directory), os.path.abspath(repository_root))
                directory_parts = relative.split(os.path.sep)
                if any(part in ('', '.', '..') for part in directory_parts):
                    raise IconError("plugin directory must be below the repository root")
                anchor = os.path.realpath(repository_root)
            fds.append(os.open(anchor, flags | os.O_DIRECTORY))
            for part in directory_parts:
                if part:
                    fds.append(os.open(part, flags | os.O_DIRECTORY, dir_fd=fds[-1]))
            for part in parts[:-1]:
                fds.append(os.open(part, flags | os.O_DIRECTORY, dir_fd=fds[-1]))
            info = os.lstat(parts[-1], dir_fd=fds[-1])
            if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
                raise IconError(f"icon is not a regular file: {icon}")
            fd = os.open(parts[-1], flags | os.O_NONBLOCK, dir_fd=fds[-1])
        except FileNotFoundError:
            raise IconError(f"missing icon file: {icon}")
        except OSError as error:
            raise IconError(f"cannot open icon {icon}: {error.strerror}")
        with os.fdopen(fd, "rb") as handle:
            if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                raise IconError(f"icon is not a regular file: {icon}")
            data = handle.read(MAX_ICON_BYTES + 1)
    finally:
        for fd in fds:
            os.close(fd)
    if len(data) > MAX_ICON_BYTES:
        raise IconError(f"icon exceeds {MAX_ICON_BYTES} bytes: {icon}")
    return data
