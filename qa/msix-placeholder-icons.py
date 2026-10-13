"""Generate neutral QA-only MSIX placeholder PNGs without external dependencies.

These are intentionally NOT suitable as final product branding. No licensing
or font assets used. Standard-library PNG encoder keeps build self-contained.
"""
from __future__ import annotations
import struct
import sys
import zlib
from pathlib import Path

def chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(
        ">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

def icon(path: Path, size: int) -> None:
    # High contrast neutral QA icon. No user details or copyrighted imagery.
    rows = bytearray()
    for y in range(size):
        rows.append(0)
        for x in range(size):
            border = x < size // 12 or y < size // 12 or x >= size-size//12 or y >= size-size//12
            cross = abs(x-y) < max(1,size//18) or abs((size-1-x)-y) < max(1,size//18)
            if border:
                rgba = (29, 41, 57, 255)
            elif cross:
                rgba = (240, 240, 240, 255)
            else:
                rgba = (77, 90, 108, 255)
            rows.extend(rgba)
    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
           + chunk(b"IDAT", zlib.compress(bytes(rows), 6)) + chunk(b"IEND", b""))
    with path.open("xb") as f:
        f.write(png)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python msix-placeholder-icons.py <assets-directory>")
    dest = Path(sys.argv[1]).resolve()
    dest.mkdir(parents=True, exist_ok=True)
    for name, px in [("StoreLogo.png", 50),
                     ("Square44x44Logo.png", 44),
                     ("Square150x150Logo.png", 150)]:
        icon(dest / name, px)
    print("QA_PLACEHOLDER_ICONS_CREATED_NOT_FOR_STORE_RELEASE")
