#!/usr/bin/env python3
"""
Build script for aflacha.com.
Reads CMS markdown content files, generates HTML sections,
and injects them into template.html to produce index.html.

No external dependencies — contains a minimal YAML parser.
"""

import os
import re

# ── Minimal YAML Parser ──────────────────────────────────────────
# Handles the subset of YAML used in Decap CMS content files:
#   key: "value"
#   list_key:
#     - field1: "val1"
#       field2: "val2"

def parse_yaml(text):
    """Parse a simple YAML string and return a dict.
    Supports quoted values (double or single), unquoted values,
    and lists of items with nested fields."""
    result = {}
    lines = text.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.rstrip()

        # Skip empty lines and comments
        if not stripped.strip() or stripped.strip().startswith('#'):
            i += 1
            continue

        # Detect list item: `  - field: value`
        list_match = re.match(r'^(\s*)-\s+(\S+?)\s*:\s*(.*)', stripped)
        if list_match:
            # This shouldn't happen at top level — lists are children
            i += 1
            continue

        # Top-level key-value or list key
        kv_match = re.match(r'^(\S[^:]*?)\s*:\s*(.*)', stripped)
        if not kv_match:
            i += 1
            continue

        key = kv_match.group(1).strip()
        value_raw = kv_match.group(2).strip()

        if not value_raw:
            # Could be a list introduction (key with no value, children follow)
            # Check next lines for list items
            items = []
            j = i + 1
            while j < len(lines):
                next_line = lines[j]
                # Find first list item
                item_match = re.match(r'^(\s+)-\s+', next_line)
                if not item_match:
                    break
                # Check we're at a deeper indent level than the key
                indent = len(item_match.group(1))
                if indent <= len(line) - len(line.lstrip()):
                    break

                # Parse this list item's fields
                item = {}
                k = j
                # The first line of a list item is `  - field: value`
                # Parse the field from the same line as the dash
                first_line = lines[k]
                first_match = re.match(r'^(\s+)-\s+(\S+?)\s*:\s*(.*)', first_line)
                if first_match:
                    findent = len(first_match.group(1))
                    fkey = first_match.group(2)
                    fval = first_match.group(3).strip()
                    fval, k = _consume_value(lines, k, findent, fval)
                    item[fkey] = fval
                    k += 1

                # Parse remaining fields on subsequent lines
                while k < len(lines):
                    l = lines[k]
                    # Check if this line is the start of the next list item
                    li_start = re.match(r'^(\s+)-\s+', l)
                    if li_start:
                        break

                    # Check if this is a sub-field continuation
                    field_match = re.match(r'^(\s+)(\S+?)\s*:\s*(.*)', l)
                    if field_match:
                        findent = len(field_match.group(1))
                        # Field should be indented more than the list dash
                        if findent > indent:
                            fkey = field_match.group(2)
                            fval = field_match.group(3).strip()
                            fval, k = _consume_value(lines, k, findent, fval)
                            item[fkey] = fval
                            k += 1
                            continue
                        else:
                            break
                    elif l.strip() == '':
                        k += 1
                        continue
                    else:
                        break

                items.append(item)
                j = k

            if items:
                result[key] = items
                i = j
                continue

            i += 1
            continue

        # Simple key: value
        value = value_raw
        value, i = _consume_value(lines, i, len(line) - len(line.lstrip()), value_raw)
        result[key] = value
        i += 1

    return result


def _consume_value(lines, start_idx, indent, initial):
    """Read a value, handling quoted strings, YAML block scalars, and multi-line continuations."""
    value = initial

    # Remove surrounding quotes
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        value = value[1:-1]
    elif len(value) >= 2 and value[0] == "'" and value[-1] == "'":
        value = value[1:-1]

    # Handle YAML block scalar indicators (| and >)
    # When value is just '|' or '>', the actual content starts on the next line(s)
    is_block_scalar = value in ('|', '>', '|-', '>-', '|+', '>+')
    if is_block_scalar:
        value = ''

    idx = start_idx + 1
    while idx < len(lines):
        line = lines[idx]
        stripped = line.rstrip()

        # Continuation lines: same or greater indent, no new key
        leading = len(line) - len(line.lstrip())
        if leading < indent + 1:
            break

        # Check it's not a new key-value pair
        if re.match(r'^\s+\S+?:\s', stripped) or re.match(r'^\s+-\s', stripped):
            break

        if stripped.strip() == '':
            idx += 1
            continue

        # It's a continuation line
        # Use newline for block scalars, space for inline continuations
        if is_block_scalar:
            if value:
                value += '\n' + stripped.strip()
            else:
                value = stripped.strip()
        else:
            if value:
                value += ' ' + stripped.strip()
            else:
                value = stripped.strip()
        idx += 1

    return value, idx - 1


# ── Content Parsing ───────────────────────────────────────────────

CONTENT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'content')


def read_content(filename):
    """Read a content markdown file and parse it as YAML.
    Strips optional YAML frontmatter (--- ... ---) if present."""
    path = os.path.join(CONTENT_DIR, filename)
    with open(path, 'r', encoding='utf-8') as f:
        text = f.read()
    
    # Strip YAML frontmatter (--- ... ---)
    if text.startswith('---'):
        end = text.find('---', 3)
        if end != -1:
            text = text[3:end]  # Keep content BETWEEN the markers
    
    return parse_yaml(text.strip())


# ── HTML Generation ───────────────────────────────────────────────

def html_escape(text):
    """Escape HTML special characters (for safe inline use)."""
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    text = text.replace('"', '&quot;')
    return text


def generate_tagline_html(tagline):
    """Generate tagline paragraph HTML."""
    return (
        '      <p class="hero-tagline">\n'
        f'        {tagline}\n'
        '      </p>'
    )


def generate_about_html(about):
    """Generate about text paragraphs HTML."""
    bios = []
    if 'bio1' in about:
        bios.append(about['bio1'])
    if 'bio2' in about:
        bios.append(about['bio2'])
    if 'bio3' in about:
        bios.append(about['bio3'])

    paragraphs = []
    for bio in bios:
        paragraphs.append(f'          <p>\n            {bio}\n          </p>')

    return '\n'.join(paragraphs)


def generate_services_html(services_data):
    """Generate the full services grid HTML including wrapper."""
    items = services_data.get('services', [])
    cards = []
    for item in items:
        icon = item.get('icon', '')
        title = item.get('title', '')
        desc = item.get('description', '')
        card = (
            '        <div class="service-card">\n'
            f'          <div class="icon">{icon}</div>\n'
            f'          <h3>{title}</h3>\n'
            f'          <p>{desc}</p>\n'
            '        </div>'
        )
        cards.append(card)

    grid = '      <div class="services-grid">\n'
    grid += '\n'.join(cards)
    grid += '\n      </div>'
    return grid


def generate_portfolio_html(portfolio_data):
    """Generate the full portfolio grid HTML including wrapper."""
    items = portfolio_data.get('projects', [])
    cards = []
    for idx, item in enumerate(items):
        icon = item.get('icon', '')
        title = item.get('title', '')
        tag = item.get('tag', '')
        desc = item.get('description', '')
        card = (
            '\n        <!-- Project {} -->\n'
            '        <div class="portfolio-card">\n'
            f'          <div class="portfolio-thumb">{icon}</div>\n'
            '          <div class="portfolio-info">\n'
            f'            <span class="tag">{tag}</span>\n'
            f'            <h3>{title}</h3>\n'
            f'            <p>{desc}</p>\n'
            '          </div>\n'
            '        </div>'
        ).format(idx + 1)
        cards.append(card)

    grid = '      <div class="portfolio-grid">'
    grid += '\n'.join(cards)
    grid += '\n\n      </div>'
    return grid


def generate_contact_intro_html(intro):
    """Generate contact intro paragraph."""
    return (
        f'          <p>{intro}</p>'
    )


def generate_contact_email_html(email):
    """Generate the contact email link HTML."""
    return (
        '            <a href="mailto:' + email + '" class="contact-link">\n'
        '              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>\n'
        '              ' + email + '\n'
        '            </a>'
    )


# ── Main Build Logic ──────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PATH = os.path.join(BASE_DIR, 'template.html')
CONSTRUCTION_TEMPLATE_PATH = os.path.join(BASE_DIR, 'template-construction.html')
OUTPUT_PATH = os.path.join(BASE_DIR, 'index.html')


def replace_marker(text, marker_name, replacement):
    """Replace content between <!--CMS:MARKER_NAME--> and <!--/CMS:MARKER_NAME-->."""
    start_tag = f'<!--CMS:{marker_name}-->'
    end_tag = f'<!--/CMS:{marker_name}-->'

    start_idx = text.find(start_tag)
    if start_idx == -1:
        print(f"  WARNING: Start marker {start_tag} not found in template")
        return text

    end_idx = text.find(end_tag, start_idx)
    if end_idx == -1:
        print(f"  WARNING: End marker {end_tag} not found in template")
        return text

    # Move start_idx back to beginning of the marker line (after preceding newline)
    # so the indent before the marker is also replaced
    line_start = text.rfind('\n', 0, start_idx)
    content_start = line_start + 1 if line_start != -1 else 0

    # Include the end tag and the newline after it (if present) to avoid blank lines
    content_end = end_idx + len(end_tag)
    if content_end < len(text) and text[content_end] == '\n':
        content_end += 1

    new_text = text[:content_start] + replacement + '\n' + text[content_end:]
    return new_text


def build():
    print("Building aflacha.com...")

    # Check under_construction toggle
    print("  Checking settings...")
    settings = read_content('settings.md')
    under_construction = settings.get('under_construction', False)
    # Handle both boolean and string values (YAML stores as true/false)
    if isinstance(under_construction, str):
        under_construction = under_construction.lower() in ('true', 'yes', '1')
    
    if under_construction:
        print("    → Under Construction mode ON")
        # Just copy the construction template
        print("  Reading construction template...")
        with open(CONSTRUCTION_TEMPLATE_PATH, 'r', encoding='utf-8') as f:
            html = f.read()
    else:
        print("    → Full portfolio mode")
        # 1. Parse content files
        print("  Reading content files...")
        about = read_content('about.md')
        services_data = read_content('services.md')
        portfolio_data = read_content('portfolio.md')
        contact = read_content('contact.md')

        print(f"    About: {len(about)} fields")
        print(f"    Services: {len(services_data.get('services', []))} items")
        print(f"    Portfolio: {len(portfolio_data.get('projects', []))} items")
        print(f"    Contact: {len(contact)} fields")

        # 2. Read template
        print("  Reading template...")
        with open(TEMPLATE_PATH, 'r', encoding='utf-8') as f:
            html = f.read()

        # 3. Generate replacements
        print("  Generating HTML sections...")

        tagline_html = generate_tagline_html(about.get('tagline', ''))
        html = replace_marker(html, 'TAGLINE', tagline_html)
        print("    ✓ Tagline")

        about_html = generate_about_html(about)
        html = replace_marker(html, 'ABOUT_TEXT', about_html)
        print("    ✓ About text")

        services_html = generate_services_html(services_data)
        html = replace_marker(html, 'SERVICES_CARDS', services_html)
        print("    ✓ Services cards")

        portfolio_html = generate_portfolio_html(portfolio_data)
        html = replace_marker(html, 'PORTFOLIO_CARDS', portfolio_html)
        print("    ✓ Portfolio cards")

        contact_intro_html = generate_contact_intro_html(contact.get('intro', ''))
        html = replace_marker(html, 'CONTACT_INTRO', contact_intro_html)
        print("    ✓ Contact intro")

        contact_email_html = generate_contact_email_html(contact.get('email', ''))
        html = replace_marker(html, 'CONTACT_EMAIL', contact_email_html)
        print("    ✓ Contact email")

    # 4. Write output
    print("  Writing index.html...")
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        f.write(html)

    print("  Done! ✓")


if __name__ == '__main__':
    build()
