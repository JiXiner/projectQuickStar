"""Lightweight, dependency-free source summaries used by generated reports."""

from __future__ import annotations

import ast
import re
from pathlib import Path

from .language_detector import language_for_path

MAX_ANALYZED_FILE_SIZE = 2 * 1024 * 1024


def analyze_source_file(path: Path) -> dict | None:
    """Describe a source/configuration file without executing its content."""

    language = language_for_path(path)
    suffix = path.suffix.lower()
    supported_auxiliary = {
        ".yml", ".yaml", ".json", ".xml", ".properties", ".ini", ".toml",
        ".env", ".sql", ".md", ".rst",
    }
    if language is None and suffix not in supported_auxiliary and not path.name.lower().startswith("readme"):
        return None
    try:
        if path.stat().st_size > MAX_ANALYZED_FILE_SIZE:
            return {
                "purpose": infer_file_purpose(path),
                "language": language_for_path(path) or file_type(path),
                "line_count": 0,
                "imports": [],
                "symbols": [],
                "notes": ["文件超过 2 MB，已跳过代码级解析"],
            }
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    if language == "Python":
        return _analyze_python(path, text)
    if language in {"Java", "JavaScript", "PHP", "Go"}:
        return _analyze_brace_language(path, text, language)
    if suffix in {".yml", ".yaml", ".json", ".xml", ".properties", ".ini", ".toml", ".env"}:
        return _analyze_config(path, text)
    if suffix == ".sql":
        return _analyze_sql(path, text)
    if path.name.lower().startswith("readme") or suffix in {".md", ".rst"}:
        return _base_analysis(path, text, "文档")
    return None


def infer_file_purpose(path: Path) -> str:
    """Infer a useful responsibility from conventional enterprise naming."""

    normalized = "/".join(path.parts).lower()
    name = path.stem.lower()
    rules = (
        (("controller", "handler", "endpoint"), "接口/请求处理层：接收请求、校验参数并调用业务服务"),
        (("service", "usecase", "use_case"), "业务服务层：编排核心业务规则与上下游调用"),
        (("repository", "dao", "mapper"), "数据访问层：封装数据库读写和对象映射"),
        (("model", "entity", "domain", "schema", "dto", "vo"), "领域/数据模型：定义业务对象及数据结构"),
        (("config", "setting", "properties"), "配置模块：定义应用参数、组件装配或环境设置"),
        (("middleware", "interceptor", "filter"), "中间件：处理跨业务请求逻辑、鉴权或日志"),
        (("route", "router", "urls"), "路由模块：声明外部接口与处理器映射"),
        (("client", "gateway", "adapter"), "外部集成层：封装远程服务或第三方系统调用"),
        (("util", "helper", "common"), "公共工具模块：提供可复用的辅助能力"),
        (("test", "spec"), "自动化测试：验证业务或基础设施行为"),
        (("migration", "ddl"), "数据库变更：维护表结构或数据迁移"),
        (("component", "view", "page"), "界面组件：负责页面展示与用户交互"),
        (("main", "app", "application", "manage", "index"), "应用入口：初始化组件并启动程序"),
    )
    for tokens, purpose in rules:
        if any(token in name or f"/{token}/" in f"/{normalized}/" for token in tokens):
            return purpose
    suffix_purposes = {
        ".sql": "数据库脚本：定义或操作数据库结构与数据",
        ".yml": "YAML 配置：描述应用、部署或自动化参数",
        ".yaml": "YAML 配置：描述应用、部署或自动化参数",
        ".json": "JSON 配置/数据：保存结构化参数或元数据",
        ".xml": "XML 配置/映射：保存结构化配置或数据映射",
        ".properties": "应用属性配置：保存运行环境参数",
        ".md": "项目文档：说明设计、使用方式或开发约定",
    }
    return suffix_purposes.get(path.suffix.lower(), "源码模块：提供与文件名对应的业务或基础能力")


def _base_analysis(path: Path, text: str, language: str) -> dict:
    return {
        "purpose": infer_file_purpose(path),
        "language": language,
        "line_count": len(text.splitlines()),
        "imports": [],
        "symbols": [],
        "notes": [],
    }


def _analyze_python(path: Path, text: str) -> dict:
    result = _base_analysis(path, text, "Python")
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        result["notes"].append(f"语法解析失败（第 {exc.lineno or '?'} 行）：{exc.msg}")
        return result

    imports: list[str] = []
    symbols: list[dict] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            imports.extend(f"{module}.{alias.name}".strip(".") for alias in node.names)
        elif isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if isinstance(node, ast.ClassDef):
                kind = "类"
                signature = node.name
            else:
                kind = "异步函数" if isinstance(node, ast.AsyncFunctionDef) else "函数/方法"
                args = [argument.arg for argument in node.args.args]
                signature = f"{node.name}({', '.join(args)})"
            doc = ast.get_docstring(node, clean=True)
            symbols.append(
                {
                    "kind": kind,
                    "name": node.name,
                    "line": node.lineno,
                    "signature": signature,
                    "purpose": _short_doc(doc) or infer_symbol_purpose(node.name, kind),
                }
            )
    result["imports"] = sorted(set(imports))[:100]
    result["symbols"] = sorted(symbols, key=lambda item: item["line"])
    module_doc = ast.get_docstring(tree, clean=True)
    if module_doc:
        result["purpose"] = _short_doc(module_doc)
    return result


def _analyze_brace_language(path: Path, text: str, language: str) -> dict:
    result = _base_analysis(path, text, language)
    patterns = {
        "Java": [
            ("类/接口", r"(?m)^\s*(?:public\s+|private\s+|protected\s+)?(?:abstract\s+)?(?:class|interface|enum|record)\s+(\w+)"),
            ("方法", r"(?m)^\s*(?:public|private|protected|static|final|synchronized|abstract|native|\s)+[\w<>,?\[\].]+\s+(\w+)\s*\(([^;{}]*)\)\s*(?:throws[^\{]+)?\{"),
        ],
        "JavaScript": [
            ("类", r"(?m)^\s*(?:export\s+)?class\s+(\w+)"),
            ("函数", r"(?m)^\s*(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)"),
            ("函数", r"(?m)^\s*(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\(([^)]*)\)\s*=>"),
        ],
        "PHP": [
            ("类/接口", r"(?mi)^\s*(?:abstract\s+|final\s+)?(?:class|interface|trait)\s+(\w+)"),
            ("函数/方法", r"(?mi)^\s*(?:public|private|protected|static|final|abstract|\s)*function\s+(\w+)\s*\(([^)]*)\)"),
        ],
        "Go": [
            ("结构/接口", r"(?m)^\s*type\s+(\w+)\s+(?:struct|interface)\s*\{"),
            ("函数/方法", r"(?m)^\s*func\s*(?:\([^)]*\)\s*)?(\w+)\s*\(([^)]*)\)"),
        ],
    }
    symbols = []
    for kind, pattern in patterns[language]:
        for match in re.finditer(pattern, text):
            name = match.group(1)
            arguments = match.group(2).strip() if match.lastindex and match.lastindex >= 2 else ""
            symbols.append(
                {
                    "kind": kind,
                    "name": name,
                    "line": text.count("\n", 0, match.start()) + 1,
                    "signature": f"{name}({arguments})" if match.lastindex and match.lastindex >= 2 else name,
                    "purpose": infer_symbol_purpose(name, kind),
                }
            )
    result["symbols"] = sorted(symbols, key=lambda item: item["line"])
    import_patterns = {
        "Java": r"(?m)^\s*import\s+(?:static\s+)?([\w.*]+)\s*;",
        "JavaScript": r"(?m)^\s*import\s+.*?\s+from\s+['\"]([^'\"]+)",
        "PHP": r"(?mi)^\s*(?:use|require|include)(?:_once)?\s*\(?['\"]?([^;'\")]+)",
        "Go": r"(?m)^\s*\"([^\"]+)\"\s*$",
    }
    result["imports"] = sorted(set(re.findall(import_patterns[language], text)))[:100]
    return result


def _analyze_config(path: Path, text: str) -> dict:
    result = _base_analysis(path, text, "配置")
    keys = re.findall(r"(?m)^\s*[\"']?([A-Za-z_][\w.-]*)[\"']?\s*[:=]", text)
    result["symbols"] = [
        {"kind": "配置项", "name": key, "line": 0, "signature": key, "purpose": "配置参数"}
        for key in list(dict.fromkeys(keys))[:50]
    ]
    return result


def _analyze_sql(path: Path, text: str) -> dict:
    result = _base_analysis(path, text, "SQL")
    symbols = []
    for action, name in re.findall(r"(?is)\b(CREATE\s+TABLE|ALTER\s+TABLE|INSERT\s+INTO|UPDATE|DELETE\s+FROM)\s+[`\"]?([\w.]+)", text):
        symbols.append(
            {"kind": "SQL", "name": name, "line": 0, "signature": f"{action.upper()} {name}", "purpose": "数据库结构或数据操作"}
        )
    result["symbols"] = symbols
    return result


def infer_symbol_purpose(name: str, kind: str) -> str:
    words = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name).replace("_", " ").lower()
    rules = (
        (("get", "find", "query", "list", "load", "fetch"), "查询或读取数据"),
        (("create", "add", "insert", "save"), "创建并保存数据"),
        (("update", "edit", "modify"), "更新已有数据"),
        (("delete", "remove"), "删除或清理数据"),
        (("validate", "check", "verify"), "校验输入或业务条件"),
        (("login", "auth", "token"), "处理身份认证与授权"),
        (("send", "publish", "emit"), "发送消息或事件"),
        (("handle", "process", "execute", "run"), "执行核心处理流程"),
        (("parse", "convert", "transform"), "解析或转换数据"),
        (("init", "setup", "configure"), "初始化或配置组件"),
    )
    for tokens, purpose in rules:
        if any(token in words.split() for token in tokens):
            return purpose
    return f"定义{name}相关的{kind}逻辑"


def file_type(path: Path) -> str:
    return path.suffix.lstrip(".").upper() or "文件"


def _short_doc(doc: str | None) -> str | None:
    if not doc:
        return None
    first_paragraph = doc.strip().split("\n\n", 1)[0].replace("\n", " ")
    return first_paragraph[:300]
