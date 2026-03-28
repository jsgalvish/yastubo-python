"""
One-time script: convert Blade templates in template_versions to Jinja2.

Run:  python scripts/convert_templates_blade_to_jinja2.py
"""
import re
import sys
import pymysql

DB_CONFIG = dict(host="127.0.0.1", user="root", password="", database="gfa", charset="utf8mb4")


def blade_to_jinja2(content: str) -> str:
    """Convert Blade template syntax to Jinja2."""

    # 1. Blade comments  {{-- ... --}}  →  {# ... #}
    content = re.sub(r'\{\{--\s*(.*?)\s*--\}\}', r'{# \1 #}', content, flags=re.DOTALL)

    # 2. Remove @php ... @endphp blocks — convert the notes logic to Jinja2
    #    Specific: the notes accumulator pattern
    content = re.sub(
        r'@php\s*\$notes\s*=\s*\[\];\s*@endphp',
        '{% set notes = [] %}',
        content,
    )
    # The inner @php block that pushes to notes
    def convert_notes_php(m):
        return (
            '{% set n = namespace() %}\n'
            '{% set n.val = none %}\n'
            '{% if coverage.get("notes_t") %}\n'
            '{% set _ = notes.append(coverage["notes_t"]) %}\n'
            '{% set n.val = notes|length %}\n'
            '{% endif %}'
        )
    content = re.sub(
        r'@php\s*\$n\s*=\s*null;.*?@endphp',
        convert_notes_php,
        content,
        flags=re.DOTALL,
    )

    # 3. Unescaped output  {!! $expr !!}  →  {{ expr }}
    def unescaped_repl(m):
        expr = m.group(1).strip()
        expr = expr.replace('$', '').replace('->', '.')
        return '{{ %s }}' % expr
    content = re.sub(r'\{!!\s*(.+?)\s*!!\}', unescaped_repl, content)

    # 4. PHP function calls inside {{ }}
    #    {{ ucwords(strtolower($var)) }}  →  {{ var|title }}
    content = re.sub(
        r'\{\{\s*ucwords\(strtolower\(\$([^)]+)\)\)\s*\}\}',
        r'{{ \1|title }}',
        content,
    )

    # 5. Ternary inside {{ }}
    #    {{ $n ? "*({$n})" : "" }}  →  {{ "*(%d)"|format(n.val) if n.val else "" }}
    content = re.sub(
        r'\{\{\s*\$n\s*\?\s*"\*\(\{\$n\}\)"\s*:\s*""\s*\}\}',
        '{{ "*(%d)"|format(n.val) if n.val else "" }}',
        content,
    )

    # 6. {{ $i+1 }}  →  {{ loop.index }}  (inside @foreach with index)
    content = re.sub(r'\{\{\s*\$i\+1\s*\}\}', '{{ loop.index }}', content)

    # 7. Regular Blade variables  {{ $var['key'] }}  →  {{ var['key'] }}
    #    and  {{ $var->prop }}  →  {{ var.prop }}
    def blade_var_repl(m):
        expr = m.group(1).strip()
        expr = expr.replace('$', '').replace('->', '.')
        return '{{ %s }}' % expr
    content = re.sub(r'\{\{\s*\$([^}]+?)\s*\}\}', blade_var_repl, content)

    # 8. @foreach($items as $key=>$value)  →  {% for key, value in items %}
    def foreach_repl(m):
        body = m.group(1).strip()
        parts = re.split(r'\s+as\s+', body, maxsplit=1)
        if len(parts) == 2:
            collection = parts[0].strip().lstrip('$').replace('->', '.')
            item = parts[1].strip().lstrip('$').replace('->', '.')
            if '=>' in item:
                kv = item.split('=>')
                key = kv[0].strip().lstrip('$')
                val = kv[1].strip().lstrip('$')
                return '{%% for %s, %s in %s|items %%}' % (key, val, collection)
            return '{%% for %s in %s %%}' % (item, collection)
        return m.group(0)
    content = re.sub(r'@foreach\s*\(([^)]+)\)', foreach_repl, content)
    content = content.replace('@endforeach', '{% endfor %}')

    # 9. @if / @elseif / @else / @endif
    def if_repl(m):
        expr = m.group(1).strip()
        expr = expr.replace('$', '').replace('->', '.')
        # !empty(x) → x
        expr = re.sub(r'!empty\(([^)]+)\)', r'\1', expr)
        # empty(x) → not x
        expr = re.sub(r'empty\(([^)]+)\)', r'not \1', expr)
        # count(x) → x|length
        expr = re.sub(r'count\(([^)]+)\)', r'\1|length', expr)
        return '{%% if %s %%}' % expr
    content = re.sub(r'@if\s*\(([^)]+)\)', if_repl, content)

    def elseif_repl(m):
        expr = m.group(1).strip()
        expr = expr.replace('$', '').replace('->', '.')
        expr = re.sub(r'!empty\(([^)]+)\)', r'\1', expr)
        expr = re.sub(r'empty\(([^)]+)\)', r'not \1', expr)
        return '{%% elif %s %%}' % expr
    content = re.sub(r'@elseif\s*\(([^)]+)\)', elseif_repl, content)
    content = content.replace('@else', '{% else %}')
    content = content.replace('@endif', '{% endif %}')

    # 10. Unescape literal \n \t to actual characters (MySQL escaping artifact)
    content = content.replace('\\n', '\n').replace('\\t', '\t')

    return content


def main():
    conn = pymysql.connect(**DB_CONFIG)
    cur = conn.cursor()

    cur.execute("SELECT id, content FROM template_versions")
    rows = cur.fetchall()

    for row_id, blade_content in rows:
        jinja_content = blade_to_jinja2(blade_content)

        # Verify no $ remain (except in CSS or comments)
        remaining = re.findall(r'\$\w+', jinja_content)
        if remaining:
            print(f"WARNING template {row_id}: {len(remaining)} unconverted $ vars: {remaining[:5]}")

        cur.execute(
            "UPDATE template_versions SET content = %s WHERE id = %s",
            (jinja_content, row_id),
        )
        print(f"Template {row_id}: converted ({len(blade_content)} -> {len(jinja_content)} chars)")

    conn.commit()
    cur.close()
    conn.close()
    print("Done.")


if __name__ == "__main__":
    main()
