"""Self-contained HTML rendering for the source analysis report."""

from __future__ import annotations

import html
import re


def markdown_to_html(markdown: str) -> str:
    """Convert the report's controlled Markdown subset to readable HTML."""

    body: list[str] = []
    in_list = False
    in_table = False
    table_header = True
    for raw in markdown.splitlines():
        line = raw.rstrip()
        if line.startswith("|"):
            if re.match(r"^\|[-:| ]+\|$", line):
                table_header = False
                continue
            if not in_table:
                body.append("<table><thead>")
                in_table = True
                table_header = True
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            tag = "th" if table_header else "td"
            body.append("<tr>" + "".join(f"<{tag}>{_inline(cell)}</{tag}>" for cell in cells) + "</tr>")
            if table_header:
                body.append("</thead><tbody>")
            continue
        if in_table:
            body.append("</tbody></table>")
            in_table = False
        if line.startswith("- "):
            if not in_list:
                body.append("<ul>")
                in_list = True
            body.append(f"<li>{_inline(line[2:])}</li>")
            continue
        if in_list:
            body.append("</ul>")
            in_list = False
        heading = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading:
            level = len(heading.group(1))
            body.append(f"<h{level}>{_inline(heading.group(2))}</h{level}>")
        elif re.match(r"^\d+\. ", line):
            body.append(f"<p class='step'>{_inline(line)}</p>")
        elif line.startswith("> "):
            body.append(f"<blockquote>{_inline(line[2:])}</blockquote>")
        elif line == "---":
            body.append("<hr>")
        elif line:
            body.append(f"<p>{_inline(line)}</p>")
    if in_list:
        body.append("</ul>")
    if in_table:
        body.append("</tbody></table>")
    title = html.escape(markdown.splitlines()[0].lstrip("# ") if markdown else "项目分析报告")
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title><style>
body{{font-family:"Microsoft YaHei",Segoe UI,sans-serif;max-width:1200px;margin:0 auto;padding:36px;color:#263238;line-height:1.7;background:#f7f9fb}}
h1,h2,h3{{color:#123b5d}} h1{{border-bottom:3px solid #2b7bbb;padding-bottom:12px}} h2{{margin-top:36px;border-left:5px solid #2b7bbb;padding-left:12px}}
table{{width:100%;border-collapse:collapse;margin:14px 0 28px;background:white;font-size:14px}} th{{background:#e8f1f8;text-align:left}} th,td{{border:1px solid #cbd6df;padding:8px 10px;vertical-align:top}}
code{{background:#e9eef2;padding:2px 5px;border-radius:4px}} blockquote{{margin:5px 0;border-left:4px solid #8ab4d4;padding:3px 14px;color:#526673}}
p,ul{{background:white;padding:8px 14px;margin:6px 0}} ul{{padding-left:38px}} .step{{font-weight:500}}
</style></head><body>{''.join(body)}</body></html>"""


def _inline(value: str) -> str:
    escaped = html.escape(value)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    return escaped.replace("  ", "<br>")
