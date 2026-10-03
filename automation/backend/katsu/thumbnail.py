from io import BytesIO
from pathlib import Path
from uuid import uuid4
from PIL import Image, ImageDraw, ImageFont, ImageOps
from .models import Artifact
from .legacy import load
from .store import fingerprint


FONT = Path(__file__).parent / 'assets/Fredoka.ttf'
SIZE = (3840, 2160)
MAX_BYTES = 2_000_000


def headline_layout(headline):
    """Fit complete words into the reserved left side without clipping."""
    for size in range(420, 140, -6):
        font = ImageFont.truetype(str(FONT), size)
        font.set_variation_by_name('Bold')
        lines, line = [], ''
        for word in headline.split():
            candidate = (line + ' ' + word).strip()
            if line and font.getlength(candidate) > 1578:
                lines.append(line)
                line = word
            else:
                line = candidate
        lines.append(line)
        text = '\n'.join(lines)
        spacing, stroke = round(size*.12), max(6, round(size*.045))
        box = ImageDraw.Draw(Image.new('RGB', (1, 1))).multiline_textbbox((0, 0), text, font=font, spacing=spacing, stroke_width=stroke)
        if len(lines) <= 3 and box[2]-box[0] <= 1632 and box[3]-box[1] <= 1512:
            return text, font, spacing, stroke, box
    raise ValueError('The thumbnail headline will not fit. Use shorter words and try again.')


def render_thumbnail(artwork, headline, destination):
    text, font, spacing, stroke, box = headline_layout(headline)
    canvas = Image.new('RGB', SIZE, 'white')
    with Image.open(artwork) as source:
        art = ImageOps.contain(source.convert('RGB'), SIZE, Image.Resampling.LANCZOS)
        canvas.paste(art, ((SIZE[0]-art.width)//2, (SIZE[1]-art.height)//2))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, 1824, SIZE[1]), fill='white')
    height = box[3]-box[1]
    x, y = 156-box[0], (SIZE[1]-height)//2-box[1]-60
    draw.multiline_text((x, y), text, font=font, spacing=spacing, fill='#ffdf4a', stroke_width=stroke, stroke_fill='#242424')
    brand = ImageFont.truetype(str(FONT), 78)
    brand.set_variation_by_name('SemiBold')
    draw.text((156, 1940), 'KATSU THE PRINTER', font=brand, fill='#242424')
    encoded = None
    for quality in (92, 88, 84, 80, 74, 68, 60, 50):
        output = BytesIO()
        canvas.save(output, 'JPEG', quality=quality, optimize=True, progressive=True)
        if output.tell() < MAX_BYTES:
            encoded = output.getvalue()
            break
    if encoded is None:
        raise ValueError('The thumbnail could not fit the upload size limit. The saved video is still available.')
    with Image.open(BytesIO(encoded)) as verified:
        verified.load()
        if verified.size != SIZE or verified.format != 'JPEG':
            raise ValueError('Thumbnail export verification failed.')
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name+'.'+uuid4().hex+'.tmp')
    temporary.write_bytes(encoded)
    temporary.replace(destination)
    return {'headline': headline, 'dimensions': list(SIZE), 'bytes': len(encoded), 'format': 'JPEG', 'headline_lines': text.splitlines()}


def thumbnail_key(headline, artwork):
    return fingerprint([headline, load('compose_video').digest(artwork), load('compose_video').digest(FONT), SIZE, 'thumbnail-render-v1'])
