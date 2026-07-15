"""Markdown project analysis report."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime

from analyzer.project_scan import ScanResult


def render_markdown(result: ScanResult) -> str:
    extensions = Counter(record.extension or "无扩展名" for record in result.files)
    directories: dict[str, list] = defaultdict(list)
    for record in result.files:
        top = record.path.split("/", 1)[0] if "/" in record.path else "（根目录）"
        directories[top].append(record)

    lines = [
        f"# {result.project_name} 项目源码分析报告",
        "",
        f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ",
        f"> 源项目：`{result.source_path}`  ",
        f"> 分析范围：{result.selected_language}",
        "",
        "## 1. 项目概览",
        "",
        f"- 文件总数：**{result.total_files:,}**",
        f"- 项目大小：**{_human_size(result.total_bytes)}**",
        f"- 扫描耗时：**{result.duration_seconds:.3f} 秒**",
        f"- 可识别源码：**{sum(result.detected_languages.values()):,} 个**",
        "",
        "## 2. 技术栈与文件组成",
        "",
    ]
    if result.detected_languages:
        lines.extend(f"- {language}：{count:,} 个源码文件" for language, count in result.detected_languages.items())
    else:
        lines.append("- 未发现当前支持的源码语言")
    lines.extend(["", "主要文件类型：", ""])
    lines.extend(f"- `{extension}`：{count:,} 个" for extension, count in extensions.most_common(20))

    lines.extend(["", "## 3. 项目目录组成", ""])
    lines.append("| 目录/模块 | 文件数 | 主要职责 |")
    lines.append("|---|---:|---|")
    for directory, records in sorted(directories.items(), key=lambda item: (-len(item[1]), item[0].lower())):
        purposes = Counter(
            record.analysis["purpose"] for record in records if record.analysis and record.analysis.get("purpose")
        )
        purpose = purposes.most_common(1)[0][0] if purposes else "项目文件与资源"
        lines.append(f"| `{_escape(directory)}` | {len(records):,} | {_escape(purpose)} |")

    lines.extend(["", "## 4. 文件职责与代码组成", ""])
    analyzed = 0
    for record in result.files:
        analysis = record.analysis
        if not analysis:
            continue
        analyzed += 1
        lines.extend(
            [
                f"### 4.{analyzed} `{record.path}`",
                "",
                f"- **文件职责**：{analysis['purpose']}",
                f"- **类型**：{analysis['language']}",
                f"- **代码行数**：{analysis['line_count']:,}",
                f"- **文件大小**：{_human_size(record.size)}",
            ]
        )
        if analysis.get("imports"):
            imports = "、".join(f"`{item}`" for item in analysis["imports"][:30])
            lines.append(f"- **依赖/导入**：{imports}")
        symbols = analysis.get("symbols", [])
        if symbols:
            lines.extend(["", "| 代码位置 | 类型 | 名称/签名 | 作用 |", "|---:|---|---|---|"])
            for symbol in symbols:
                location = f"第 {symbol['line']} 行" if symbol.get("line") else "—"
                lines.append(
                    f"| {location} | {_escape(symbol['kind'])} | `{_escape(symbol['signature'])}` | {_escape(symbol['purpose'])} |"
                )
        else:
            lines.extend(["", "该文件未发现可列出的类、函数、方法或配置项。"])
        for note in analysis.get("notes", []):
            lines.append(f"- ⚠️ {note}")
        lines.append("")

    lines.extend(
        [
            "## 5. 阅读建议",
            "",
            "1. 先阅读 README、入口文件和配置文件，确认启动方式与外部依赖。",
            "2. 再从 Controller/Route/Handler 跟踪请求入口。",
            "3. 沿 Service/UseCase 阅读业务编排和核心规则。",
            "4. 最后查看 Repository/DAO/Mapper、SQL 与外部 Client，理解数据流和系统边界。",
            "",
            "---",
            "本报告由静态规则分析生成，不会执行被分析项目代码。文件职责和无注释符号说明为命名约定推断，建议结合业务文档复核。",
            "",
        ]
    )
    return "\n".join(lines)


def _human_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


def _escape(value: str) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")
