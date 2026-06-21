import random
from pathlib import Path

from barcode import Code128
from barcode.writer import ImageWriter


BARCODE_DIR = Path("generated_barcodes")
BARCODE_DIR.mkdir(exist_ok=True)


def generate_barcode_value(phone):
    digits = "".join(ch for ch in phone if ch.isdigit())

    if digits.startswith("998") and len(digits) >= 12:
        base = digits[:12]
    else:
        base = "998" + digits[-9:].rjust(9, "0")

    return base + str(random.randint(10, 99))


def generate_barcode_image(barcode_value):
    """
    Creates a Code128 barcode PNG image and returns its file path.

    Code128 is flexible and supports long numeric codes.
    REGOS scanner compatibility must be tested at the cash register.
    """
    file_base = BARCODE_DIR / barcode_value

    code = Code128(barcode_value, writer=ImageWriter())
    saved_path = code.save(
        str(file_base),
        options={
            "module_width": 0.28,
            "module_height": 18.0,
            "font_size": 12,
            "text_distance": 4,
            "quiet_zone": 6.5,
            "write_text": True,
        },
    )

    return saved_path
