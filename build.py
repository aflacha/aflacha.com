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


def generate_stats_html(about):
    """Generate highlight stats cards HTML."""
    items = about.get('stats', [])
    if not items:
        return ''
    cards = []
    for item in items:
        icon = item.get('icon', '')
        number = item.get('number', '')
        label = item.get('label', '')
        card = (
            '          <div class="stat-card">\n'
            f'            <div class="icon">{icon}</div>\n'
            f'            <div class="number">{number}</div>\n'
            f'            <div class="label">{label}</div>\n'
            '          </div>'
        )
        cards.append(card)

    grid = '        <div class="about-stats">\n'
    grid += '\n'.join(cards)
    grid += '\n        </div>'
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


def generate_nav_html(site):
    """Generate navigation links HTML."""
    items = site.get('nav_links', [])
    links = []
    for item in items:
        label = item.get('label', '')
        href = item.get('href', '#')
        links.append(f'        <li><a href="{href}">{label}</a></li>')
    return '\n'.join(links)


def generate_hero_badge_html(site):
    """Generate hero badge text."""
    return site.get('hero_badge', 'Available for projects')


def generate_hero_name_html(site):
    """Generate hero name content (HTML ok)."""
    return site.get('hero_name', '<span class="highlight">Aflacha Imadida</span> Rachmata')


def generate_hero_tags_html(site):
    """Generate hero tags HTML."""
    items = site.get('hero_tags', [])
    tags = []
    for item in items:
        label = item.get('label', '')
        accent = item.get('accent', False)
        cls = 'accent' if accent else ''
        tags.append(f'        <span class="hero-tag {cls}">{label}</span>')
    return '\n'.join(tags)


def generate_hero_cta_html(site):
    """Generate CTA buttons HTML."""
    primary_text = site.get('cta_primary_text', 'See My Work')
    primary_href = site.get('cta_primary_href', '#portfolio')
    secondary_text = site.get('cta_secondary_text', 'Get in Touch')
    secondary_href = site.get('cta_secondary_href', '#contact')
    return (
        f'        <a href="{primary_href}" class="btn btn-primary">{primary_text}</a>\n'
        f'        <a href="{secondary_href}" class="btn btn-outline">{secondary_text}</a>'
    )


def generate_extra_bio_html(site):
    """Generate the extra bio paragraph after CMS content."""
    bio = site.get('hero_extra_bio', '')
    return f'          <p>\n            {bio}\n          </p>'


def generate_section_header_html(label, title):
    """Generate section label + title HTML."""
    return (
        f'      <div class="section-label">{label}</div>\n'
        f'      <h2 class="section-title">{title}</h2>'
    )


def generate_writing_card_html(site):
    """Generate writing card HTML."""
    date = site.get('writing_card_date', 'Latest')
    title = site.get('writing_card_title', 'Read my articles on Medium')
    url = site.get('writing_card_url', 'https://medium.com/@aflacha')
    return (
        f'        <a href="{url}" target="_blank" rel="noopener" class="writing-card">\n'
        f'          <span class="date">{date}</span>\n'
        f'          <span class="title">{title}</span>\n'
        f'          <span class="medium-badge">Medium</span>\n'
        f'          <span class="arrow">→</span>\n'
        f'        </a>'
    )


def generate_contact_links_html(site):
    """Generate contact social links (LinkedIn, GitHub) HTML."""
    li_url = site.get('social_linkedin_url', 'https://linkedin.com/in/aflacha')
    li_text = site.get('social_linkedin_text', 'linkedin.com/in/aflacha')
    gh_url = site.get('social_github_url', 'https://github.com/aflacha')
    gh_text = site.get('social_github_text', 'github.com/aflacha')
    li_svg = '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 2.064 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/></svg>'
    gh_svg = '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C5.374 0 0 5.373 0 12c0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23A11.509 11.509 0 0112 5.803c1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576C20.566 21.797 24 17.3 24 12c0-6.627-5.373-12-12-12z"/></svg>'
    return (
        f'            <a href="{li_url}" target="_blank" rel="noopener" class="contact-link">\n'
        f'              {li_svg}\n'
        f'              {li_text}\n'
        f'            </a>\n'
        f'            <a href="{gh_url}" target="_blank" rel="noopener" class="contact-link">\n'
        f'              {gh_svg}\n'
        f'              {gh_text}\n'
        f'            </a>'
    )


def generate_footer_html(site):
    """Generate footer HTML."""
    year = site.get('footer_year', '2026')
    text = site.get('footer_text', 'Built with patience and gold')
    return (
        f'    <p>&copy; {year} &middot; <a href="https://aflacha.com">Aflacha Imadida Rachmata</a> &middot; {text}</p>'
    )


### ── Construction template generators ─────────────────────

def generate_construction_title(site):
    return site.get('construction_title', 'Aflacha Imadida Rachmata — Coming Soon')


def generate_construction_meta_desc(site):
    return site.get('construction_meta_description', 'Personal brand & portfolio of Aflacha Imadida Rachmata — COO, game designer, creator. Coming soon.')


def generate_construction_badge(site):
    return site.get('construction_badge', 'Under Construction')


def generate_construction_heading(site):
    return site.get('construction_heading', 'Aflacha Imadida Rachmata')


def generate_construction_description(site):
    return site.get('construction_description', '')


def generate_construction_social(site):
    li = site.get('construction_social_linkedin', 'https://linkedin.com/in/aflacha')
    md = site.get('construction_social_medium', 'https://medium.com/@aflacha')
    gh = site.get('construction_social_github', 'https://github.com/aflacha')
    return (
        f'      <a href="{li}" target="_blank" rel="noopener">LinkedIn</a>\n'
        f'      <a href="{md}" target="_blank" rel="noopener">Medium</a>\n'
        f'      <a href="{gh}" target="_blank" rel="noopener">GitHub</a>'
    )


def generate_construction_footer(site):
    return site.get('construction_footer', '© 2026 · aflacha.com')


def replace_marker(text, marker_name, replacement, block=False):
    """Replace content between <!--CMS:MARKER_NAME--> and <!--/CMS:MARKER_NAME-->.
    
    If block=True: replaces from the start of the marker's line (handles indentation).
    If block=False: replaces only the content between the markers (inline).
    """
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

    if block:
        # Block mode: replace from line start of marker line to after end marker
        line_start = text.rfind('\n', 0, start_idx)
        content_start = line_start + 1 if line_start != -1 else 0
        content_end = end_idx + len(end_tag)
        if content_end < len(text) and text[content_end] == '\n':
            content_end += 1
        new_text = text[:content_start] + replacement + '\n' + text[content_end:]
    else:
        # Inline mode: replace from end of start marker to start of end marker
        # and also strip the marker tags themselves
        content_start = start_idx
        content_end = end_idx + len(end_tag)
        new_text = text[:content_start] + replacement + text[content_end:]

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
    
    # Read global site settings
    print("  Reading site settings...")
    site = read_content('site.md')
    print(f"    Site: {len(site)} fields")

    if under_construction:
        print("    → Under Construction mode ON")
        print("  Reading construction template...")
        with open(CONSTRUCTION_TEMPLATE_PATH, 'r', encoding='utf-8') as f:
            html = f.read()

        # Apply site content to construction template
        html = replace_marker(html, 'CONSTRUCTION_TITLE', generate_construction_title(site))
        html = replace_marker(html, 'CONSTRUCTION_META_DESC', generate_construction_meta_desc(site))
        html = replace_marker(html, 'CONSTRUCTION_BADGE', generate_construction_badge(site))
        html = replace_marker(html, 'CONSTRUCTION_HEADING', generate_construction_heading(site))
        html = replace_marker(html, 'CONSTRUCTION_DESCRIPTION', generate_construction_description(site), block=True)
        html = replace_marker(html, 'CONSTRUCTION_SOCIAL', generate_construction_social(site), block=True)
        html = replace_marker(html, 'CONSTRUCTION_FOOTER', generate_construction_footer(site))
        print("    ✓ Construction page content")

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

        # Site-level content (inline markers)
        html = replace_marker(html, 'SITE_TITLE', site.get('title', 'Aflacha Imadida Rachmata'))
        html = replace_marker(html, 'SITE_META_DESC', site.get('meta_description', ''))
        html = replace_marker(html, 'NAV_LOGO', site.get('nav_logo', 'A'))
        html = replace_marker(html, 'HERO_BADGE', generate_hero_badge_html(site))
        html = replace_marker(html, 'HERO_NAME', generate_hero_name_html(site))

        # Block-level markers
        html = replace_marker(html, 'NAV_LINKS', generate_nav_html(site), block=True)
        html = replace_marker(html, 'HERO_TAGS', generate_hero_tags_html(site), block=True)
        html = replace_marker(html, 'HERO_CTA', generate_hero_cta_html(site), block=True)
        html = replace_marker(html, 'EXTRA_BIO', generate_extra_bio_html(site), block=True)

        about_header = generate_section_header_html(site.get('about_label', 'About'), site.get('about_title', ''))
        html = replace_marker(html, 'ABOUT_HEADER', about_header, block=True)

        services_header = generate_section_header_html(site.get('services_label', 'What I Do'), site.get('services_title', ''))
        html = replace_marker(html, 'SERVICES_HEADER', services_header, block=True)

        portfolio_header = generate_section_header_html(site.get('portfolio_label', 'Portfolio'), site.get('portfolio_title', ''))
        html = replace_marker(html, 'PORTFOLIO_HEADER', portfolio_header, block=True)

        writing_header = generate_section_header_html(site.get('writing_label', 'Writing'), site.get('writing_title', ''))
        html = replace_marker(html, 'WRITING_HEADER', writing_header, block=True)

        contact_header = generate_section_header_html(site.get('contact_label', 'Contact'), site.get('contact_title', ''))
        html = replace_marker(html, 'CONTACT_HEADER', contact_header, block=True)

        tagline_html = generate_tagline_html(about.get('tagline', ''))
        html = replace_marker(html, 'TAGLINE', tagline_html, block=True)
        print("    ✓ Tagline")

        about_html = generate_about_html(about)
        html = replace_marker(html, 'ABOUT_TEXT', about_html, block=True)
        print("    ✓ About text")

        stats_html = generate_stats_html(about)
        html = replace_marker(html, 'ABOUT_STATS', stats_html, block=True)
        print("    ✓ About stats")

        services_html = generate_services_html(services_data)
        html = replace_marker(html, 'SERVICES_CARDS', services_html, block=True)
        print("    ✓ Services cards")

        portfolio_html = generate_portfolio_html(portfolio_data)
        html = replace_marker(html, 'PORTFOLIO_CARDS', portfolio_html, block=True)
        print("    ✓ Portfolio cards")

        writing_html = generate_writing_card_html(site)
        html = replace_marker(html, 'WRITING_CARD', writing_html, block=True)
        print("    ✓ Writing card")

        contact_links_html = generate_contact_links_html(site)
        html = replace_marker(html, 'CONTACT_LINKS', contact_links_html, block=True)
        print("    ✓ Contact social links")

        # Footer (inline)
        html = replace_marker(html, 'FOOTER_YEAR', site.get('footer_year', '2026'))
        html = replace_marker(html, 'FOOTER_TEXT', site.get('footer_text', 'Built with patience and gold'))
        print("    ✓ Footer")

        contact_intro_html = generate_contact_intro_html(contact.get('intro', ''))
        html = replace_marker(html, 'CONTACT_INTRO', contact_intro_html, block=True)
        print("    ✓ Contact intro")

        contact_email_html = generate_contact_email_html(contact.get('email', ''))
        html = replace_marker(html, 'CONTACT_EMAIL', contact_email_html, block=True)
        print("    ✓ Contact email")

    # 4. Write output
    print("  Writing index.html...")
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        f.write(html)

    print("  Done! ✓")


if __name__ == '__main__':
    build()
