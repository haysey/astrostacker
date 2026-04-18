"""Generate the Haysey's Astrostacker app icon.

Features the Southern Cross constellation with pointer stars,
overlapping stacking frames, and a deep space background.
"""

import math
import random

from PIL import Image, ImageDraw, ImageFilter, ImageFont

SIZE = 1024
HALF = SIZE // 2
random.seed(42)  # reproducible star field


def radial_gradient(size, center, radius, color_inner, color_outer):
    """Create a radial gradient image."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    for y in range(size):
        for x in range(size):
            dx = x - center[0]
            dy = y - center[1]
            dist = math.sqrt(dx * dx + dy * dy)
            t = min(1.0, dist / radius)
            r = int(color_inner[0] * (1 - t) + color_outer[0] * t)
            g = int(color_inner[1] * (1 - t) + color_outer[1] * t)
            b = int(color_inner[2] * (1 - t) + color_outer[2] * t)
            a = int(color_inner[3] * (1 - t) + color_outer[3] * t)
            img.putpixel((x, y), (r, g, b, a))
    return img


def draw_star_glow(img, cx, cy, brightness, color=(255, 255, 255)):
    """Draw a glowing star with diffraction spikes."""
    draw = ImageDraw.Draw(img)

    # Outer glow layers
    for radius in range(int(brightness * 1.8), 0, -1):
        alpha = int(40 * (1 - radius / (brightness * 1.8)))
        r, g, b = color
        glow_color = (r, g, b, max(0, alpha))
        draw.ellipse(
            [cx - radius, cy - radius, cx + radius, cy + radius],
            fill=glow_color,
        )

    # Bright core
    core_r = max(2, int(brightness * 0.25))
    draw.ellipse(
        [cx - core_r, cy - core_r, cx + core_r, cy + core_r],
        fill=(255, 255, 255, 255),
    )

    # Diffraction spikes (4-point)
    spike_len = int(brightness * 1.2)
    for angle in [0, 90, 45, 135]:
        rad = math.radians(angle)
        for d in range(spike_len):
            alpha = int(180 * (1 - d / spike_len))
            sx = int(cx + d * math.cos(rad))
            sy = int(cy + d * math.sin(rad))
            if 0 <= sx < SIZE and 0 <= sy < SIZE:
                draw.point((sx, sy), fill=(255, 255, 255, alpha))
            sx2 = int(cx - d * math.cos(rad))
            sy2 = int(cy - d * math.sin(rad))
            if 0 <= sx2 < SIZE and 0 <= sy2 < SIZE:
                draw.point((sx2, sy2), fill=(255, 255, 255, alpha))


def main():
    # === Background ===
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Circular mask
    mask = Image.new("L", (SIZE, SIZE), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.ellipse([10, 10, SIZE - 10, SIZE - 10], fill=255)

    # Deep space gradient background
    bg = Image.new("RGBA", (SIZE, SIZE), (4, 6, 20, 255))
    bg_draw = ImageDraw.Draw(bg)

    # Radial gradient - darker edges, slightly lighter center
    for r in range(HALF, 0, -1):
        t = r / HALF
        red = int(8 + 18 * t)
        green = int(10 + 16 * t)
        blue = int(30 + 30 * t)
        bg_draw.ellipse(
            [HALF - r, HALF - r, HALF + r, HALF + r],
            fill=(red, green, blue, 255),
        )

    # Nebula glow (warm amber/bronze — reflects Beta Bronze release)
    nebula = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    neb_draw = ImageDraw.Draw(nebula)
    for r in range(200, 0, -1):
        alpha = int(14 * (1 - r / 200))
        neb_draw.ellipse(
            [380 - r, 280 - r, 380 + r, 280 + r],
            fill=(120, 70, 20, alpha),
        )
    bg = Image.alpha_composite(bg, nebula)

    # Second nebula patch (teal, lower area)
    nebula2 = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    neb2_draw = ImageDraw.Draw(nebula2)
    for r in range(160, 0, -1):
        alpha = int(10 * (1 - r / 160))
        neb2_draw.ellipse(
            [620 - r, 580 - r, 620 + r, 580 + r],
            fill=(20, 60, 90, alpha),
        )
    bg = Image.alpha_composite(bg, nebula2)

    # === Background star field ===
    stars_layer = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    stars_draw = ImageDraw.Draw(stars_layer)

    for _ in range(300):
        x = random.randint(20, SIZE - 20)
        y = random.randint(20, SIZE - 20)
        # Only draw if inside the circle
        if (x - HALF) ** 2 + (y - HALF) ** 2 < (HALF - 20) ** 2:
            brightness = random.randint(60, 200)
            size = random.choice([1, 1, 1, 2])
            stars_draw.ellipse(
                [x - size, y - size, x + size, y + size],
                fill=(255, 255, 255, brightness),
            )

    bg = Image.alpha_composite(bg, stars_layer)

    # === Stacking frames (3 overlapping rectangles) ===
    frames_layer = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    frames_draw = ImageDraw.Draw(frames_layer)

    frame_w, frame_h = 340, 240
    offsets = [(-25, -18), (0, 0), (25, 18)]
    for i, (ox, oy) in enumerate(offsets):
        cx = HALF + ox - 20
        cy = HALF + oy - 60
        x1 = cx - frame_w // 2
        y1 = cy - frame_h // 2
        x2 = cx + frame_w // 2
        y2 = cy + frame_h // 2

        alpha = 50 + i * 25  # progressively brighter
        color = (205, 127, 50, alpha)  # bronze frames
        # Rounded rectangle outline
        frames_draw.rounded_rectangle(
            [x1, y1, x2, y2],
            radius=8,
            outline=color,
            width=2,
        )

    bg = Image.alpha_composite(bg, frames_layer)

    # === Southern Cross constellation ===
    # Star positions (roughly accurate relative pattern, centered in icon)
    # Crux is oriented as seen from southern hemisphere
    crux_cx, crux_cy = HALF - 10, HALF - 50

    # Scale factor for the constellation
    s = 2.8

    # Southern Cross stars (relative positions)
    # Acrux (Alpha) - bottom of cross
    acrux = (crux_cx + int(0 * s), crux_cy + int(65 * s))
    # Gacrux (Gamma) - top of cross
    gacrux = (crux_cx + int(5 * s), crux_cy - int(55 * s))
    # Mimosa (Beta) - left
    mimosa = (crux_cx - int(50 * s), crux_cy + int(10 * s))
    # Delta Crucis - right
    delta = (crux_cx + int(45 * s), crux_cy - int(5 * s))
    # Epsilon Crucis - small one, slightly below-left of center
    epsilon = (crux_cx + int(18 * s), crux_cy + int(20 * s))

    # Pointer stars (Alpha & Beta Centauri) - to the left, pointing toward Crux
    alpha_cen = (crux_cx - int(95 * s), crux_cy + int(75 * s))
    beta_cen = (crux_cx - int(70 * s), crux_cy + int(55 * s))

    # Draw constellation lines (subtle)
    lines_layer = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    lines_draw = ImageDraw.Draw(lines_layer)

    line_color = (205, 140, 60, 40)  # bronze constellation lines
    lines_draw.line([gacrux, acrux], fill=line_color, width=1)
    lines_draw.line([mimosa, delta], fill=line_color, width=1)
    # Pointer line
    lines_draw.line([alpha_cen, beta_cen], fill=line_color, width=1)

    bg = Image.alpha_composite(bg, lines_layer)

    # Draw the stars with glow
    constellation_layer = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))

    # Southern Cross stars - bright blue-white
    star_color = (200, 220, 255)
    draw_star_glow(constellation_layer, *acrux, 28, star_color)   # Alpha - brightest
    draw_star_glow(constellation_layer, *mimosa, 24, star_color)  # Beta
    draw_star_glow(constellation_layer, *gacrux, 22, (255, 200, 150))  # Gamma - orange-ish
    draw_star_glow(constellation_layer, *delta, 18, star_color)   # Delta
    draw_star_glow(constellation_layer, *epsilon, 12, star_color) # Epsilon - dimmest

    # Pointer stars - warm white
    pointer_color = (255, 240, 200)
    draw_star_glow(constellation_layer, *alpha_cen, 26, pointer_color)  # Alpha Centauri
    draw_star_glow(constellation_layer, *beta_cen, 20, pointer_color)   # Beta Centauri

    bg = Image.alpha_composite(bg, constellation_layer)

    # === Circle border (bronze ring — Beta Bronze release) ===
    border_layer = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    border_draw = ImageDraw.Draw(border_layer)

    # Outer ring - bronze
    border_draw.ellipse(
        [10, 10, SIZE - 10, SIZE - 10],
        outline=(205, 127, 50, 140),
        width=3,
    )
    # Inner thin ring - dimmer bronze
    border_draw.ellipse(
        [18, 18, SIZE - 18, SIZE - 18],
        outline=(205, 127, 50, 50),
        width=1,
    )

    bg = Image.alpha_composite(bg, border_layer)

    # === Apply circular mask ===
    # Create final image with black background outside circle
    final = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 255))
    final.paste(bg, mask=mask)

    # Soften slightly for a polished look
    final = final.filter(ImageFilter.SMOOTH)

    # Save outputs
    final.save("icon.png", "PNG")
    print(f"Saved icon.png ({SIZE}x{SIZE})")

    # Also save a 256x256 for .ico
    icon_256 = final.resize((256, 256), Image.LANCZOS)
    icon_256.save("icon_256.png", "PNG")
    print("Saved icon_256.png (256x256)")


if __name__ == "__main__":
    main()
