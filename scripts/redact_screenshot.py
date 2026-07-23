#!/usr/bin/env python3
"""Apply a soft, rounded privacy blur to screenshot regions."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


def parse_region(value: str) -> tuple[int, int, int, int]:
    try:
        coordinates = tuple(int(part) for part in value.split(","))
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "regions must use x1,y1,x2,y2 integer coordinates"
        ) from error

    if len(coordinates) != 4:
        raise argparse.ArgumentTypeError(
            "regions must use x1,y1,x2,y2 integer coordinates"
        )

    x1, y1, x2, y2 = coordinates
    if x2 <= x1 or y2 <= y1:
        raise argparse.ArgumentTypeError("region bounds must have positive area")
    return x1, y1, x2, y2


def redact_region(
    image: Image.Image,
    region: tuple[int, int, int, int],
    *,
    blur_radius: int,
    feather: int,
    corner_radius: int,
) -> None:
    x1, y1, x2, y2 = region
    crop = image.crop(region)
    blurred = crop.filter(ImageFilter.GaussianBlur(blur_radius))

    # A light darkening layer keeps the redaction at home in Hedra's dark UI.
    tint = Image.new("RGBA", blurred.size, (10, 10, 10, 52))
    blurred = Image.alpha_composite(blurred.convert("RGBA"), tint)

    mask = Image.new("L", blurred.size, 0)
    draw = ImageDraw.Draw(mask)
    inset = max(1, feather)
    draw.rounded_rectangle(
        (inset, inset, blurred.width - inset, blurred.height - inset),
        radius=corner_radius,
        fill=255,
    )
    mask = mask.filter(ImageFilter.GaussianBlur(feather))
    image.paste(blurred, region, mask)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--region",
        action="append",
        default=[],
        type=parse_region,
        help="privacy region as x1,y1,x2,y2; repeat for multiple regions",
    )
    parser.add_argument("--blur-radius", type=int, default=24)
    parser.add_argument("--feather", type=int, default=5)
    parser.add_argument("--corner-radius", type=int, default=14)
    arguments = parser.parse_args()

    image = Image.open(arguments.input).convert("RGBA")
    for region in arguments.region:
        redact_region(
            image,
            region,
            blur_radius=arguments.blur_radius,
            feather=arguments.feather,
            corner_radius=arguments.corner_radius,
        )

    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(arguments.output, optimize=True, quality=92)


if __name__ == "__main__":
    main()
