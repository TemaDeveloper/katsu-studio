from pathlib import Path
import shutil
from .store import atomic_json

WORKSPACE = Path(__file__).resolve().parents[3]
AUTOMATION = WORKSPACE / 'automation'


def channel_profile(root):
    channel = root / 'channel'
    channel.mkdir(exist_ok=True)
    assets = {
        'avatar.png': WORKSPACE / 'output/channel_branding/katsu-avatar-150.png',
        'reference.png': WORKSPACE / 'output/images/shot-001.png',
    }
    for name, source in assets.items():
        if not source.is_file():
            source = Path(__file__).parent / 'assets' / name
        if not (channel / name).exists() and source.is_file():
            shutil.copy2(source, channel / name)
    style = {'name': 'Katsu The Printer', 'style': 'Original humorous hand-drawn explainer. Mostly white background, thick uneven black outlines, oversized white oval heads, thin black stick limbs, gray shading. Main character has one black hair curl, black oval eyes and expressive mouth with coral tongue; no clothing. Yellow and coral accents. Clear visual metaphors, no copied channel art. Landscape composition; still illustrations, direct cuts. Do not draw labels or text; the editor adds any labels separately.'}
    profile = channel / 'profile.json'
    if not profile.exists():
        atomic_json(profile, style)
    import json
    return json.loads(profile.read_text())
