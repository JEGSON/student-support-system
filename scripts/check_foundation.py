
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit, unquote
import csv
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs:
            self.ids.add(attrs['id'])
        for key in ('src', 'href'):
            if attrs.get(key):
                self.links.append(attrs[key])


def records(relative):
    with (ROOT / relative).open(newline='') as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        assert rows and reader.fieldnames, f'Empty register: {relative}'
        assert all(None not in row and None not in row.values() for row in rows), relative
        return rows


def identifiers(relative, field, expected):
    rows = records(relative)
    ids = [row[field] for row in rows]
    assert len(ids) == len(set(ids)), f'Duplicate IDs: {relative}'
    assert set(ids) == expected, f'Missing/unexpected IDs: {relative}'
    return rows


def numbered(prefix, count):
    return {f'{prefix}{i:02}' for i in range(1, count + 1)}


def check_link(value, parent):
    url = urlsplit(value)
    if url.scheme or url.netloc:
        return
    target = (parent / unquote(url.path)).resolve() if url.path else parent
    assert target.is_relative_to(ROOT), f'Link outside repository: {value}'
    assert target.exists(), f'Missing local target: {value}'
    if url.fragment and target.suffix == '.html':
        parser = Links()
        parser.feed(target.read_text())
        assert unquote(url.fragment) in parser.ids, f'Missing anchor: {value}'


def main():
    req_ids = numbered('FR-', 13) | numbered('SR-', 11) | numbered('BR-', 10) | numbered('C-', 7)
    req = identifiers('docs/requirements/register.csv', 'requirement_id', req_ids)
    workflows = identifiers('docs/requirements/workflows.csv', 'workflow_id', numbered('WF-', 11))
    risks = identifiers('docs/security/risk-register.csv', 'risk_id', numbered('T', 12))
    tests = identifiers('docs/testing/verification-plan.csv', 'test_id', numbered('V', 16))
    identifiers('docs/decisions/architecture-decisions.csv', 'decision_id', numbered('ADR-', 9))
    ods = identifiers('docs/decisions/open-decisions.csv', 'decision_id', numbered('OD-', 8))
    backlog = identifiers('docs/development/backlog.csv', 'stage', {f'{i:02}' for i in range(2, 20)})
    assert all(r['depends_on_stage'] == f"{int(r['stage']) - 1:02}" for r in backlog)
    assert all(r['owner_role_proposed'] and r['demonstration_impact'] and r['production_or_assessment_gate'] for r in ods)
    trace = records('docs/testing/traceability.csv')
    for field, expected in [('requirement_id', req_ids), ('workflow_id', numbered('WF-', 11)),
                            ('threat_id', numbered('T', 12)), ('test_id', numbered('V', 16))]:
        found = {item for row in trace for item in row[field].split()}
        assert found == expected, f'Traceability mismatch: {field}'
    assert all(r['status'] in {'not run', 'partial', 'passed', 'failed'} for r in tests)
    assert all(r['evidence_reference'] for r in tests if r['status'] != 'not run')
    assert all(r['residual_status'] == 'unverified; not accepted' for r in risks)
    assert all(r['status'] == 'unresolved' for r in req if r['requirement_id'] in {'FR-04', 'FR-06'})
    for row in trace:
        assert row['primary_stage'] in {f'{i:02}' for i in range(1, 20)}
        for field in ('implementation_reference', 'evidence_reference'):
            if row[field]:
                check_link(row[field], ROOT)
    for file in ROOT.glob('docs/**/*.csv'):
        for row in records(file.relative_to(ROOT)):
            if row.get('source'):
                check_link(row['source'], ROOT)
    link_count = 0
    for file in [ROOT / 'README.md', *ROOT.glob('docs/**/*.md'), *ROOT.glob('docs/**/*.html')]:
        if file.suffix == '.html':
            parser = Links()
            parser.feed(file.read_text())
            links = parser.links
        else:
            links = re.findall(r'\[[^\]]+\]\(([^)]+)\)', file.read_text())
        for value in links:
            if value.startswith('#'):
                check_link(file.name + value, file.parent)
            else:
                check_link(value, file.parent)
            link_count += 1
    architecture = ET.parse(ROOT / 'docs/architecture/student-support-architecture.drawio').getroot()
    diagrams = architecture.findall('diagram')
    assert len(diagrams) == 8
    for diagram in diagrams:
        cells = list(diagram.iter('mxCell'))
        ids = [cell.get('id') for cell in cells]
        assert len(ids) == len(set(ids)), 'Duplicate diagram cell ID'
        for cell in cells:
            for attr in ('parent', 'source', 'target'):
                if cell.get(attr):
                    assert cell.get(attr) in ids, f'Dangling diagram {attr}'
    previews = sorted((ROOT / 'docs/architecture/architecture-previews').glob('*.png'))
    assert len(previews) == 8
    assert all(p.read_bytes().startswith(b'\x89PNG\r\n\x1a\n') for p in previews)
    print(f'PASS: {len(req)} requirements/constraints; {len(workflows)} workflows; '
          f'{len(risks)} threats; {len(tests)} verification records; 9 ADRs; 8 ODs; 18 backlog stages')
    print(f'PASS: {len(trace)} traceability rows; {link_count} document links; '
          '8 diagram graphs and PNG assets')
    print('PASS: planning integrity only; see verification register for actual runtime coverage.')


if __name__ == '__main__':
    main()
