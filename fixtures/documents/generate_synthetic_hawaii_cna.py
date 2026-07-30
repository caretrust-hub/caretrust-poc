"""Generate the deterministic synthetic CNA PNG and Textract-shaped replay.

This generator uses only the Python standard library so the fixture can be
reproduced in a clean clone without adding an imaging dependency.
"""

from __future__ import annotations

import json
import struct
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "synthetic-hawaii-cna.source.json"
PNG_PATH = HERE / "synthetic-hawaii-cna.png"
TEXTRACT_PATH = HERE / "synthetic-hawaii-cna.textract.json"

FONT = {
    " ": ("00000",) * 7,
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01111", "10000", "10000", "10000", "10000", "10000", "01111"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01111", "10000", "10000", "10111", "10001", "10001", "01111"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("11111", "00100", "00100", "00100", "00100", "00100", "11111"),
    "J": ("00111", "00010", "00010", "00010", "10010", "10010", "01100"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "Q": ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "10101", "01010"),
    "X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    "Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00010", "00100", "01000", "11111"),
    "3": ("11110", "00001", "00001", "01110", "00001", "00001", "11110"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "5": ("11111", "10000", "10000", "11110", "00001", "00001", "11110"),
    "6": ("01110", "10000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00001", "01110"),
    ":": ("00000", "00100", "00100", "00000", "00100", "00100", "00000"),
    "/": ("00001", "00010", "00010", "00100", "01000", "01000", "10000"),
    "-": ("00000", "00000", "00000", "11111", "00000", "00000", "00000"),
    ".": ("00000", "00000", "00000", "00000", "00000", "00110", "00110"),
}


def _chunk(kind: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
    )


def render_png(lines: list[str], *, width: int, height: int, scale: int) -> bytes:
    pixels = [bytearray([255]) * width for _ in range(height)]

    def fill(left: int, top: int, box_width: int, box_height: int, shade: int) -> None:
        for y in range(max(top, 0), min(top + box_height, height)):
            pixels[y][max(left, 0) : min(left + box_width, width)] = bytes(
                [shade]
            ) * max(0, min(left + box_width, width) - max(left, 0))

    fill(24, 24, width - 48, 4, 30)
    fill(24, height - 28, width - 48, 4, 30)
    fill(24, 24, 4, height - 48, 30)
    fill(width - 28, 24, 4, height - 48, 30)
    char_advance = 6 * scale
    line_advance = 11 * scale
    start_x = 60
    start_y = 62
    for line_number, line in enumerate(lines):
        y = start_y + line_number * line_advance
        for char_number, character in enumerate(line.upper()):
            glyph = FONT.get(character)
            if glyph is None:
                raise ValueError(f"unsupported fixture glyph: {character!r}")
            x = start_x + char_number * char_advance
            for row, pattern in enumerate(glyph):
                for column, bit in enumerate(pattern):
                    if bit == "1":
                        fill(
                            x + column * scale,
                            y + row * scale,
                            scale,
                            scale,
                            18,
                        )

    raw = b"".join(b"\x00" + bytes(row) for row in pixels)
    signature = b"\x89PNG\r\n\x1a\n"
    header = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    return (
        signature
        + _chunk(b"IHDR", header)
        + _chunk(b"IDAT", zlib.compress(raw, level=9))
        + _chunk(b"IEND", b"")
    )


def textract_response(
    lines: list[str],
    confidences: list[float],
    *,
    width: int,
    height: int,
    scale: int,
) -> dict[str, object]:
    blocks: list[dict[str, object]] = []
    char_advance = 6 * scale
    line_height = 7 * scale
    line_advance = 11 * scale
    start_x = 60
    start_y = 62
    for line_index, (line, confidence) in enumerate(zip(lines, confidences, strict=True)):
        top = start_y + line_index * line_advance
        line_id = f"line-{line_index + 1:02d}"
        word_ids: list[str] = []
        search_from = 0
        for word_index, word in enumerate(line.split(), start=1):
            character_index = line.index(word, search_from)
            search_from = character_index + len(word)
            word_id = f"word-{line_index + 1:02d}-{word_index:02d}"
            word_ids.append(word_id)
            blocks.append(
                {
                    "BlockType": "WORD",
                    "Confidence": max(confidence - 0.2, 0),
                    "Text": word,
                    "Page": 1,
                    "Id": word_id,
                    "Geometry": {
                        "BoundingBox": {
                            "Width": len(word) * char_advance / width,
                            "Height": line_height / height,
                            "Left": (start_x + character_index * char_advance) / width,
                            "Top": top / height,
                        }
                    },
                }
            )
        blocks.append(
            {
                "BlockType": "LINE",
                "Confidence": confidence,
                "Text": line,
                "Page": 1,
                "Id": line_id,
                "Relationships": [{"Type": "CHILD", "Ids": word_ids}],
                "Geometry": {
                    "BoundingBox": {
                        "Width": len(line) * char_advance / width,
                        "Height": line_height / height,
                        "Left": start_x / width,
                        "Top": top / height,
                    }
                },
            }
        )
    return {
        "DocumentMetadata": {"Pages": 1},
        "Blocks": blocks,
        "DetectDocumentTextModelVersion": "retained-synthetic-shape-v1",
        "ResponseMetadata": {"RequestId": "retained-synthetic-no-aws-call"},
    }


def main() -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    png = render_png(
        source["rendered_lines"],
        width=source["width"],
        height=source["height"],
        scale=source["scale"],
    )
    response = textract_response(
        source["retained_ocr_lines"],
        source["line_confidence"],
        width=source["width"],
        height=source["height"],
        scale=source["scale"],
    )
    PNG_PATH.write_bytes(png)
    TEXTRACT_PATH.write_text(
        json.dumps(response, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
