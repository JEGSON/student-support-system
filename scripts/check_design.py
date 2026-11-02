"""Static checks for isolated synthetic design artefacts; no browser assurance."""
from html.parser import HTMLParser
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / 'docs/design/prototypes'


def luminance(value):
    channels = [int(value[i:i+2], 16) / 255 for i in (0, 2, 4)]
    channels = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in channels]
    return sum(v * w for v, w in zip(channels, (.2126, .7152, .0722)))


def contrast(a, b):
    low, high = sorted((luminance(a), luminance(b)))
    return (high + .05) / (low + .05)


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.fields = set()
        self.labels = set()
        self.h1 = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'h1':
            self.h1 += 1
        if tag in ('input', 'select', 'textarea'):
            self.fields.add(a['id'])
        if tag == 'label':
            self.labels.add(a['for'])
        if tag == 'script':
            raise AssertionError('Static prototypes should not load scripts')
        for attr in ('src', 'href'):
            assert not a.get(attr, '').startswith(('http:', 'https:', '//')), 'Remote asset/link'


def main():
    pages = list(DESIGN.glob('*.html'))
    assert len(pages) == 8
    for file in pages:
        text = file.read_text()
        page = Page()
        page.feed(text)
        assert page.h1 == 1 and page.fields <= page.labels, file
        assert 'synthetic' in text.lower()
        assert 'localStorage' not in text and '<form' not in text
    # Student projections must not contain the distinctive staff note fixture.
    fixture = 'Discuss available support options at the next review.'
    for name in ('index', 'overview', 'request', 'case'):
        assert fixture not in (DESIGN / f'{name}.html').read_text()
        assert 'id="note"' not in (DESIGN / f'{name}.html').read_text()
    pairs = [
        ('ink/canvas', '172e3b', 'f7f6f2', 4.5),
        ('muted/surface', '53656b', 'ffffff', 4.5),
        ('white/teal', 'ffffff', '12675f', 4.5),
        ('teal/tint', '12675f', 'e9f3ef', 4.5),
        ('amber/panel', '704e16', 'faf0d9', 4.5),
        ('error/panel', '9d3435', 'fff0ee', 4.5),
        ('field border/white', '788b88', 'ffffff', 3),
        ('focus/canvas', '145dba', 'f7f6f2', 3),
    ]
    ratios = {name: round(contrast(a, b), 2) for name, a, b, _ in pairs}
    assert all(contrast(a, b) >= minimum for _, a, b, minimum in pairs)
    print('PASS: eight synthetic static pages; one h1 and labelled fields; no remote requests/scripts/forms')
    print('PASS: student pages omit staff-note fixture and composer; contrast pairs:', json.dumps(ratios))
    print('Rendered layout, keyboard and accessibility checks are not covered.')


if __name__ == '__main__':
    main()
