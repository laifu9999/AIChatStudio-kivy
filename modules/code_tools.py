# -*- coding: utf-8 -*-
"""代码生成与代码修复工具模块。

能力：
1. 扫描整个目录，提取所有源文件内容
2. 一次发送给 AI 进行整体分析
3. 解析 AI 返回的代码修改指令（```replace 块或 ```file 块），自动应用
4. 支持大目录批量修复（不中断）
5. 智能记忆：记住用户的历史修改偏好

输出格式（AI 回复中）：
- ```file <path>    <content>   ```    创建/覆盖整个文件
- ```replace <path>    <old> -> <new>```  在文件中做精确替换
- ```append <path>     <content>```     在文件末尾追加
"""
import os
import re
import shutil
import fnmatch
from pathlib import Path
from typing import List, Tuple, Dict, Optional


# 智能忽略：扫描时不读取这些目录/文件（防止把构建产物/二进制提交给 AI）
IGNORE_DIRS = {
    "__pycache__", ".git", ".svn", ".hg", "node_modules", "venv", "env",
    ".venv", ".tox", "dist", "build", ".idea", ".vscode", ".pytest_cache",
    "target", "out", "bin", "obj", ".gradle", ".m2",
}
IGNORE_EXT = {
    ".pyc", ".pyo", ".class", ".o", ".obj", ".so", ".dll", ".exe",
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg",
    ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".mp3", ".mp4", ".wav", ".avi", ".mov", ".mkv",
    ".lock", ".sum", ".mod", ".tmp", ".bak", ".swp",
}

# 支持读取的源文件后缀
SOURCE_EXT = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".kt", ".go",
    ".c", ".cc", ".cpp", ".cxx", ".h", ".hpp", ".hxx",
    ".cs", ".rs", ".rb", ".php", ".sh", ".bash", ".ps1",
    ".html", ".htm", ".css", ".scss", ".sass", ".less",
    ".json", ".yaml", ".yml", ".toml", ".xml", ".ini", ".cfg",
    ".md", ".rst", ".txt", ".sql", ".lua", ".r", ".scala", ".swift",
    ".dart", ".vue", ".svelte", ".qml", ".glsl",
    # PyQt5 / Kivy
    ".kv", ".qss", ".ui",
}


def is_source_file(path: str) -> bool:
    p = Path(path)
    if p.suffix.lower() in IGNORE_EXT:
        return False
    if p.suffix.lower() in SOURCE_EXT:
        return True
    return False


def scan_directory(root: str, max_files: int = 200, max_total_chars: int = 800_000) -> List[Tuple[str, str]]:
    """扫描目录，提取所有源文件内容。

    返回 [(相对路径, 文件内容), ...]
    - max_files: 最多扫描文件数（避免提交过大目录）
    - max_total_chars: 总字符数上限（避免 token 超限）
    """
    root_p = Path(root).resolve()
    results: List[Tuple[str, str]] = []
    total_chars = 0
    file_count = 0

    if not root_p.exists() or not root_p.is_dir():
        return results

    for dirpath, dirnames, filenames in os.walk(root_p):
        # 过滤忽略目录
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS and not d.startswith(".")]

        for fn in filenames:
            if file_count >= max_files:
                break
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root_p).replace(os.sep, "/")
            if not is_source_file(full):
                continue
            try:
                with open(full, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
            except Exception:
                continue
            # 超大文件跳过（防止单文件 token 超限）
            if len(content) > 50_000:
                results.append((rel, f"/* 跳过：文件超过 50KB ({len(content)} chars) */"))
            else:
                results.append((rel, content))
            total_chars += len(content) + len(rel) + 10
            file_count += 1
            if total_chars > max_total_chars:
                # 已达上限，截断
                results.append(("[TRUNCATED]", f"扫描达到字符上限 {max_total_chars}，已截断；剩余文件未读取"))
                return results
    return results


def parse_code_blocks(ai_reply: str) -> List[Dict[str, str]]:
    """解析 AI 回复中的代码修改指令。

    支持的块：
    - ```file <path> ... ```   创建/覆盖整个文件
    - ```replace <path> ... ``` 在文件中做精确替换（AI 自己说明 old → new）
    - ```append <path> ... ```  追加到文件末尾
    - ```delete <path> ... ```  删除文件
    - ```create_dir <path> ... ``` 创建目录

    鲁棒性：
    - 支持更多别名：mkdir/folder/new_folder/md → mkdir；save/create/new_file → write；touch → 空文件
    - 当 file/write/save 块【没有】路径参数时，自动从内容中提取文件名
      （兼容 AI 常见的 "文件名：xxx"、"file: xxx"、首行 "# xxx.py" 写法），避免整块被跳过
    """
    blocks = []
    # 匹配 ```lang path ... ```  格式（path 可省略；支持引号包裹的含空格路径）
    pat = re.compile(
        r"```(\w+)(?:\s+(?:\"([^\"\n]+)\"|'([^'\n]+)'|(\S+)))?\s*\n(.*?)```",
        re.S,
    )
    for m in pat.finditer(ai_reply):
        lang = (m.group(1) or "").lower().strip()
        raw_path = (m.group(2) or m.group(3) or m.group(4) or "").strip()
        content = m.group(5)
        # 容错：AI 常把"文件名：xxx"写在 path 位置（其实是内容首行）。
        # 若捕获到的 path 不像真实路径（无扩展名/分隔符/盘符，或含中文冒号），
        # 则视为无显式路径，把这一行并回内容，再尝试从内容提取文件名。
        if raw_path and not _looks_like_explicit_path(raw_path):
            # 该行其实是文件名标注（如"文件名：xxx"）或被误判的纯文件名，
            # 先尝试从中提取真实文件名；提取不到且本身不像文件名（无扩展名）则跳过该块
            extracted = _extract_filename_from_content(raw_path)
            if extracted:
                path = extracted
            elif _looks_like_path(raw_path):
                path = _clean_path(raw_path)
            else:
                path = ""  # 既不是显式路径也不是文件名，跳过
            raw_path = ""
        else:
            path = raw_path
        # 仅处理受支持的指令
        if lang in ("file", "create_file", "write", "new_file", "create", "overwrite", "save"):
            # 没有显式路径 → 尝试从内容里提取文件名
            if not path:
                path = _extract_filename_from_content(content)
            if not path:
                continue
            blocks.append({"op": "write", "path": path, "content": content})
        elif lang in ("touch", "newfile"):
            if not path:
                path = _extract_filename_from_content(content)
            if not path:
                continue
            blocks.append({"op": "write", "path": path, "content": ""})
        elif lang in ("replace", "patch", "edit", "modify"):
            if not path:
                path = _extract_filename_from_content(content)
            if not path:
                continue
            # 解析 content 里的 old / new 标记
            old, new = _parse_replace_content(content)
            blocks.append({"op": "replace", "path": path, "old": old, "new": new})
        elif lang in ("append", "concat"):
            if not path:
                path = _extract_filename_from_content(content)
            if not path:
                continue
            blocks.append({"op": "append", "path": path, "content": content})
        elif lang in ("delete", "rm", "remove"):
            if not path:
                path = _extract_filename_from_content(content)
            if not path:
                continue
            blocks.append({"op": "delete", "path": path})
        elif lang in ("create_dir", "mkdir", "make_dir", "folder", "new_folder", "md"):
            if not path:
                path = _extract_filename_from_content(content)
            if not path:
                continue
            blocks.append({"op": "mkdir", "path": path})
        elif lang in ("savebody", "save_body", "savetext"):
            # 长篇正文保存：块内只写保存路径（不含正文），正文由「本条消息正文」注入。
            # 注意：解析器可能把块首行当成「路径参数」放入 raw_path，这里优先用 raw_path 还原路径。
            spec = (raw_path or content or "").strip()
            m = re.match(r"^@save:\s*(.+)$", spec, re.I)
            path = m.group(1).strip() if m else spec
            path = _clean_path(path)
            if not path:
                continue
            blocks.append({"op": "savebody", "path": path, "content": ""})
    return blocks


def _looks_like_explicit_path(s: str) -> bool:
    """判断捕获到的 path 参数是否看起来像一个显式文件路径/目录路径。

    显式路径通常含：扩展名( .xxx )、目录分隔符( / 或 \\ )、或 Windows 盘符( C: )。
    像 "文件名：hello.txt" 这种（含中文冒号、无分隔符、扩展名前是中文）应判定为「非路径」。
    """
    if not s:
        return False
    if ":" in s and not re.match(r"^[A-Za-z]:", s):
        return False  # 含非盘符冒号（如中文"："或 "文件名："）→ 不是路径
    if "\\" in s or "/" in s:
        return True
    if re.match(r"^[A-Za-z]:", s):
        return True
    # 含扩展名且无空格、且为纯 ASCII（排除"文件名：xxx"这类中文行）→ 视为显式文件
    if "." in s and " " not in s and s.isascii():
        return True
    return False


def _extract_filename_from_content(content: str) -> str:
    """当代码块未写路径参数时，从内容里尽力提取一个文件名。

    兼容常见写法：
    - 首行 "文件名：xxx.txt" / "file: xxx.txt" / "路径: xxx"
    - 首行 "# xxx.py"（脚本 shebang/标题）
    - 内容里出现的第一个看起来像 `xxx.ext` 的 token
    返回提取到的相对路径（不含分隔符前缀），失败返回 ""。
    """
    if not content:
        return ""
    first = content.strip().splitlines()[0].strip() if content.strip() else ""
    # 1) 文件名：/ file: / 路径: 等显式标注
    m = re.match(r"^(?:文件名|文件|file|path|路径)\s*[:：]\s*(.+)$", first, re.I)
    if m:
        cand = m.group(1).strip().strip("`\"'")
        if _looks_like_path(cand):
            return _clean_path(cand)
    # 2) 首行 "# xxx.py" 或 "/* xxx.py */"
    m = re.match(r"^[#/*\s-]*([\w\-./\\]+\.[A-Za-z0-9]+)\s*$", first)
    if m:
        cand = m.group(1).strip()
        if _looks_like_path(cand):
            return _clean_path(cand)
    # 3) 内容里第一个像文件名的 token（含扩展名）
    for line in content.splitlines():
        for tok in re.findall(r"[\w\-./\\]+\.[A-Za-z0-9]{1,10}", line):
            if _looks_like_path(tok) and not tok.startswith("."):
                return _clean_path(tok)
    return ""


def _looks_like_path(s: str) -> bool:
    """粗略判断一个字符串是否像一个文件路径（含扩展名、非纯语句）。"""
    if not s:
        return False
    if len(s) > 260:
        return False
    # 必须含扩展名
    if "." not in s:
        return False
    # 排除明显是句子的情况（太长无分隔符）
    if " " in s and ("/" not in s and "\\" not in s):
        return False
    return True


def _clean_path(s: str) -> str:
    """清理提取到的路径：去掉引号/反引号/首尾空白，去掉盘符外的非法前缀。"""
    s = s.strip().strip("`\"'").strip()
    # 去掉可能的 markdown 链接包裹
    s = re.sub(r"[\[\]\(\)]", "", s)
    return s


def _parse_replace_content(content: str) -> Tuple[str, str]:
    """解析 replace 块内容：尝试拆出 old / new。"""
    # 常见格式1：@@OLD@@...@@NEW@@...
    if "@@OLD@@" in content and "@@NEW@@" in content:
        try:
            old = content.split("@@OLD@@", 1)[1].split("@@NEW@@", 1)[0].strip("\n")
            new = content.split("@@NEW@@", 1)[1].strip("\n")
            return old, new
        except Exception:
            pass
    # 常见格式2：old -> new   （单行/简单）
    if "->" in content:
        parts = content.split("->", 1)
        if len(parts) == 2:
            return parts[0].strip(), parts[1]
    # 默认：整段视为新内容
    return "", content


# ---------------- PowerShell 文件操作兜底解析 ----------------
PS_FILE_OP_VERBS = re.compile(
    r"(\[System\.IO\.File\]::WriteAllText\b|WriteAllText\b|New-Item\s+-ItemType\s+(Directory|File)|"
    r"mkdir\b|md\b|Set-Content\b|Add-Content\b|Out-File\b|Remove-Item\b)",
    re.I,
)


def _ps_str_param(line: str, param: str) -> str:
    """从 PowerShell 命令行中提取 -Param \"value\" 或 -Param 'value' 的值；找不到返回 None。"""
    # PowerShell 双引号字符串里，转义引号是 ""；反斜杠是路径分隔符，按字面处理
    pat = r'-\b%s\b\s+"((?:[^"]|"")*)"' % re.escape(param)
    m = re.search(pat, line, re.I)
    if m:
        return m.group(1).replace('""', '"')
    # 单引号字符串里，转义引号是 ''
    pat = r"-\b%s\b\s+'((?:[^']|'')*)'" % re.escape(param)
    m = re.search(pat, line, re.I)
    if m:
        return m.group(1).replace("''", "'")
    return None


def _ps_path_param(line: str) -> str:
    """提取 -Path 或 -LiteralPath 参数的值。"""
    return _ps_str_param(line, "Path") or _ps_str_param(line, "LiteralPath")


def _extract_write_all_text(line: str) -> Tuple[Optional[str], Optional[str]]:
    """解析 [System.IO.File]::WriteAllText(...) / WriteAllText(...) 的 path/value。
    若 value 是 $env:CHAT_BODY 或 %%BODY%% 等变量/占位符则返回 (path, None)，
    让调用方跳过兜底、交给执行器注入。
    """
    m = re.search(
        r'(?:\[System\.IO\.File\]::)?WriteAllText\s*\(\s*'
        r'(?:"((?:[^"]|"")*)"|\'((?:[^\']|\'\')*)\')\s*,\s*'
        r'(?:"((?:[^"]|"")*)"|\'((?:[^\']|\'\')*)\'|(\$[\w:]+|%?%BODY%?%))',
        line,
        re.I,
    )
    if not m:
        return None, None
    path = m.group(1) if m.group(1) is not None else m.group(2)
    path = path.replace('""', '"').replace("''", "'")
    # value 是变量/占位符：不在这里兜底提取
    if m.group(5) is not None:
        return path, None
    value = (m.group(3) if m.group(3) is not None else m.group(4))
    value = value.replace('""', '"').replace("''", "'")
    return path, value


def extract_file_markers(body: str) -> List[Dict[str, str]]:
    """解析正文中的 %%FILE:相对路径%% 标记，返回可写入的文件操作列表。

    格式示例（所有模型都会，零重复 token）：
        %%FILE:卷一/第一章.txt%%
        第一章正文内容……
        %%FILE:卷一/第二章.txt%%
        第二章正文内容……

    路径前的空白与尾部的空白会被 trim；正文保留原样（含换行）。
    返回 [{"op": "write", "path": "...", "content": "..."}, ...]
    """
    if not body:
        return []
    ops: List[Dict[str, str]] = []
    # 匹配：%%FILE:路径%% 后跟随内容，直到下一个 %%FILE: 或文本结束
    pat = re.compile(r"%%FILE:\s*(.+?)%%\s*(.*?)(?=%%FILE:|$)", re.S)
    for m in pat.finditer(body):
        path = m.group(1).strip().strip("`\"'")
        path = _clean_path(path)
        content = m.group(2)
        # 去掉内容末尾因正则贪婪可能产生的多余空行，但保留内部换行
        content = content.rstrip("\n")
        if path:
            ops.append({"op": "write", "path": path, "content": content})
    return ops


def strip_file_markers(body: str) -> str:
    """把 %%FILE:路径%% 标记从正文中移除，用于聊天显示层（避免显示混乱）。"""
    if not body:
        return body
    # 先去掉 %%FILE:路径%% 标记本身，保留后面的正文内容
    text = re.sub(r"%%FILE:\s*(.+?)%%", "", body, flags=re.S)
    # 把连续空行压缩
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_file_ops_from_powershell(code: str) -> List[Dict[str, str]]:
    """从 PowerShell 代码中提取文件/目录操作，作为 AI 未使用专用代码块时的兜底。

    返回的 op 与 parse_code_blocks 兼容：write / mkdir / append / delete。
    支持 -Force、-ErrorAction、| Out-Null 等尾部参数；支持参数顺序互换；
    支持 [System.IO.File]::WriteAllText 这种单行保存写法。
    """
    ops: List[Dict[str, str]] = []

    for raw in code.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        # [System.IO.File]::WriteAllText("path", "value")
        if re.search(r'WriteAllText\s*\(', line, re.I):
            path, value = _extract_write_all_text(line)
            if path and value is not None:
                ops.append({"op": "write", "path": path, "content": value})
            # value 是 $env:CHAT_BODY / %%BODY%% 等变量时，不在这里兜底，
            # 由 main_window 跳过兜底交给 powershell() 注入；纯路径错误则跳过。
            continue

        # mkdir / md "path" 或 'path'（允许尾部空格/参数）
        m = re.match(r'^(?:mkdir|md)\s+(?:"([^"]+)"|\'([^\']+)\')', line, re.I)
        if m:
            ops.append({"op": "mkdir", "path": m.group(1) if m.group(1) is not None else m.group(2)})
            continue

        # New-Item 目录 / 文件（参数顺序任意，允许尾部 -Force / -ErrorAction / | Out-Null）
        if re.match(r'^New-Item\b', line, re.I):
            path = _ps_path_param(line)
            value = _ps_str_param(line, "Value")
            if re.search(r'-ItemType\s+Directory\b', line, re.I):
                if path is not None:
                    ops.append({"op": "mkdir", "path": path})
                    continue
            elif re.search(r'-ItemType\s+File\b', line, re.I):
                if path is not None and value is not None:
                    ops.append({"op": "write", "path": path, "content": value})
                    continue

        # Set-Content / Add-Content
        if re.match(r'^(?:Set-Content|Add-Content)\b', line, re.I):
            path = _ps_path_param(line)
            value = _ps_str_param(line, "Value")
            # 也支持位置参数：Set-Content "path" "value"
            if path is None:
                m = re.match(
                    r'^(?:Set-Content|Add-Content)\s+(?:"([^"]+)"|\'([^\']+)\')\s+(?:"([^"]*)"|\'([^\']*)\')',
                    line,
                    re.I,
                )
                if m:
                    path = m.group(1) if m.group(1) is not None else m.group(2)
                    value = m.group(3) if m.group(3) is not None else m.group(4)
            if path is not None and value is not None:
                op = "append" if re.match(r'^Add-Content\b', line, re.I) else "write"
                ops.append({"op": op, "path": path, "content": value})
                continue

        # Out-File -FilePath "path" -InputObject "value"
        if re.match(r'^Out-File\b', line, re.I):
            path = _ps_str_param(line, "FilePath") or _ps_path_param(line)
            value = _ps_str_param(line, "InputObject") or _ps_str_param(line, "Value")
            if path is not None and value is not None:
                ops.append({"op": "write", "path": path, "content": value})
                continue

        # Remove-Item -Path "path" / -LiteralPath "path" / "path"
        if re.match(r'^Remove-Item\b', line, re.I):
            path = _ps_path_param(line)
            if path is None:
                m = re.match(r'^Remove-Item\s+(?:-Path\s+|[-/]\w+\s+)?"([^"]+)"', line, re.I)
                if not m:
                    m = re.match(r"^Remove-Item\s+(?:-Path\s+|[-/]\w+\s+)?'([^']+)'", line, re.I)
                if m:
                    path = m.group(1)
            if path is not None:
                ops.append({"op": "delete", "path": path})
                continue

    return ops


def apply_blocks(blocks: List[Dict[str, str]], base_dir: str, body: str = None) -> List[str]:
    """应用代码修改指令到 base_dir 下的文件。返回操作日志。

    body：本条 AI 消息的「正文」（不含代码块），供 savebody 操作把正文写入文件，
    实现「正文只写一遍、同时又分类保存」的目标。
    """
    logs: List[str] = []
    for b in blocks:
        op = b.get("op")
        path = b.get("path", "").lstrip("/").replace("/", os.sep)
        if not path:
            logs.append("[!] 跳过：无路径的块")
            continue
        full = os.path.join(base_dir, path)
        try:
            # 目标目录：有父目录用父目录，否则直接用 base_dir（避免误写到 cwd）
            parent_dir = os.path.dirname(full) or base_dir
            if op == "write":
                os.makedirs(parent_dir, exist_ok=True)
                with open(full, "w", encoding="utf-8") as f:
                    f.write(b.get("content", ""))
                logs.append(f"[OK] 写入: {path} ({len(b.get('content', ''))} chars)")
            elif op == "replace":
                if not os.path.exists(full):
                    logs.append(f"[!] 跳过 replace: {path} 不存在")
                    continue
                with open(full, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read()
                old, new = b.get("old", ""), b.get("new", "")
                if not old:
                    # 没有 old，整段视为新内容直接覆盖
                    new_text = new
                elif old in text:
                    new_text = text.replace(old, new, 1)
                else:
                    logs.append(f"[!] replace 失败: {path} 找不到匹配的 old 片段（前 60 字符：{old[:60]!r}）")
                    continue
                with open(full, "w", encoding="utf-8") as f:
                    f.write(new_text)
                logs.append(f"[替换] 替换: {path}")
            elif op == "append":
                os.makedirs(parent_dir, exist_ok=True)
                with open(full, "a", encoding="utf-8") as f:
                    f.write(b.get("content", ""))
                logs.append(f"[追加] 追加: {path} ({len(b.get('content', ''))} chars)")
            elif op == "delete":
                if os.path.exists(full):
                    if os.path.isdir(full):
                        shutil.rmtree(full)
                        logs.append(f"[删] 删除目录: {path}")
                    else:
                        os.remove(full)
                        logs.append(f"[删] 删除: {path}")
                else:
                    logs.append(f"[!] 跳过 delete: {path} 不存在")
            elif op == "mkdir":
                os.makedirs(full, exist_ok=True)
                logs.append(f"[目录] 创建目录: {path}")
            elif op == "savebody":
                # 把「本条消息正文」保存为该路径文件：正文只写一遍，聊天与文件内容一致
                body_text = (b.get("body") or body or "").strip()
                if not body_text:
                    logs.append(f"[!] 跳过 savebody: {path}（本条消息没有可保存的正文）")
                    continue
                os.makedirs(parent_dir, exist_ok=True)
                with open(full, "w", encoding="utf-8") as f:
                    f.write(body_text)
                logs.append(f"[正文] 正文已保存: {path} ({len(body_text)} 字)")
            else:
                logs.append(f"[!] 未知操作: {op}")
        except Exception as e:
            logs.append(f"[失败] 失败 {op} {path}: {e}")
    return logs


def build_project_prompt(root: str, task: str, files: List[Tuple[str, str]],
                         mode: str = "fix") -> str:
    """构造发给 AI 的项目级提示词。"""
    lines = [
        f"# 任务：{task}",
        "",
        f"目标目录：{root}",
        "",
    ]
    if mode in ("fix", "fix_all"):
        lines.extend([
            "## 修复模式",
            "请扫描下方所有源文件，找出 bug / 错误 / 不规范之处，并给出修改方案。",
            ("注意：这是整个项目文件夹，请逐文件、逐处检查并修复【所有】问题，绝不能遗漏任何一个文件或任何一处错误；"
             "即使文件很多，也要全部覆盖，不要只修一部分。" if mode == "fix_all" else ""),
            "",
            "## 输出格式",
            "请用以下代码块表达每个修改：",
            "",
            "**修改文件中某段代码（推荐）**：",
            "```replace <相对路径>",
            "@@OLD@@",
            "原来的代码片段（精确匹配，整段复制）",
            "@@NEW@@",
            "改成的新代码",
            "```",
            "",
            "**创建/覆盖整个文件**：",
            "```file <相对路径>",
            "完整文件内容",
            "```",
            "",
            "**追加内容到文件末尾**：",
            "```append <相对路径>",
            "要追加的内容",
            "```",
            "",
            "**删除文件/目录**：",
            "```delete <相对路径>",
            "```",
            "",
            "**创建目录**：",
            "```create_dir <相对路径>",
            "```",
            "",
            "## 要求",
            "- 优先使用 `replace`，最小改动原则",
            "- 一个修复一个块，不要一次塞多个修改到同一个块",
            "- 旧片段必须能在原文中精确找到（包含缩进和换行）",
            "- 完成后请简要说明修改原因",
        ])
    elif mode == "generate":
        lines.extend([
            "## 生成模式",
            "用户希望基于以下已有代码基础，生成/扩展/重写某些模块。",
            "请仔细阅读下方所有文件，然后给出实现代码。",
            "",
            "## 输出格式",
            "- 新文件用 ```file <相对路径> ... ```",
            "- 修改已有文件用 ```replace <相对路径> ... ```",
            "- 追加用 ```append <相对路径> ... ```",
            "",
            "## 要求",
            "- 保持与已有代码风格一致",
            "- 不要删除已有功能，只新增/扩展",
            "- 给出关键文件即可，不必重复输出所有文件",
        ])
    elif mode == "review":
        lines.extend([
            "## 审查模式",
            "请对下方代码做 code review：",
            "- 潜在 bug 与边界情况",
            "- 性能瓶颈",
            "- 安全漏洞（SQL 注入 / XSS / 路径穿越等）",
            "- 代码风格与可读性",
            "",
            "如果发现必须修复的严重问题，请直接用 `replace`/`file` 块给出修复；",
            "其他建议直接用文字列出即可。",
        ])
    lines.extend(["", "## 项目文件", ""])
    for rel, content in files:
        lines.append(f"=== FILE: {rel} ===")
        lines.append(content)
        lines.append(f"=== END {rel} ===")
        lines.append("")
    return "\n".join(lines)


def build_file_fix_prompt(path: str, content: str, task: str) -> str:
    """构造单文件修复提示词：只针对一个文件做精准修复。"""
    lines = [
        f"# 任务：{task}",
        "",
        f"目标文件：{path}",
        "请只针对下面这一个文件进行修复，不要改动其它文件。",
        "",
        "## 要求",
        "1. 优先使用 `replace` 块做最小改动（如下面格式）。",
        "2. 如果问题较多或不适合局部替换，可以直接用 `file` 块给出该文件的【完整修复后内容】，"
        "我会用该内容整体覆盖文件。",
        "3. 旧片段（replace 的 @@OLD@@）必须能在原文中精确匹配（含缩进与换行）。",
        "4. 修复完成后简要说明改了什么、为什么。",
        "",
        "## 输出格式",
        "```replace <相对路径>",
        "@@OLD@@",
        "原来的代码片段（整段精确复制）",
        "@@NEW@@",
        "改成的新代码",
        "```",
        "",
        "或整文件覆盖：",
        "```file <相对路径>",
        "修复后的完整文件内容",
        "```",
        "",
        "## 待修复文件内容",
        f"=== FILE: {path} ===",
        content,
        f"=== END {path} ===",
        "",
    ]
    return "\n".join(lines)

def build_simple_generate_prompt(requirement: str) -> str:
    """无项目上下文时，单纯让 AI 写一段代码（小型应用/脚本）。"""
    return f"""# 任务：{requirement}

## 你的角色
你是一位经验丰富的全栈工程师，可以写任意语言、任意规模的代码。

## 输出格式
- 多个文件用多个代码块，每个用 ```file <相对路径> 开头
- 单文件脚本用 ```code 块即可
- 写完代码后简要说明运行方法

## 关键要求
1. 直接给完整可运行代码，不要只给片段
2. 包含必要的 import / 依赖说明
3. 如有多个文件，用 ASCII 目录树说明结构
4. 大型项目请分模块组织

## 开始写代码：
"""


def _match_source_files(patterns: List[str], base: str) -> List[str]:
    """根据 glob 模式匹配文件。"""
    matches = []
    for pat in patterns:
        for root, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            for f in files:
                if fnmatch.fnmatch(f, pat):
                    matches.append(os.path.join(root, f))
    return matches


def chunk_files(files, max_chunk_chars=350_000):
    """把扫描到的文件列表按字符数切块，避免单次请求超出模型上下文。

    返回 [[(rel, content), ...], ...]，每块累计字符数 <= max_chunk_chars。
    """
    chunks = []
    cur = []
    cur_chars = 0
    for rel, content in files:
        c = len(content) + len(rel) + 12
        if cur and cur_chars + c > max_chunk_chars:
            chunks.append(cur)
            cur = []
            cur_chars = 0
        cur.append((rel, content))
        cur_chars += c
    if cur:
        chunks.append(cur)
    return chunks


def build_fix_all_chunk_prompt(task, chunk_files, chunk_index, total_chunks,
                               fixed_so_far, root=""):
    """构造「分块修复」某一块的提示词，携带已修复记忆。

    - chunk_files: 本块要检查/修复的文件 [(rel, content)]
    - chunk_index / total_chunks: 当前第几块 / 总块数
    - fixed_so_far: 之前块已经修过的文件相对路径列表（记忆，避免重复/遗漏）
    """
    lines = [
        f"# 分块修复任务（第 {chunk_index}/{total_chunks} 块）",
        "",
        f"总体目标：{task}",
        f"项目根目录：{root}",
        "",
        "## 这是一次「分多次」修复中的一块",
        f"- 你正在修复第 {chunk_index} 块，共 {total_chunks} 块。",
        "- 请只针对【下面这一块】的文件进行修复，不要修改其它文件。",
        "- 之前已经修复过的文件（记忆，勿重复修复）："
        + (", ".join(fixed_so_far) if fixed_so_far else "（无，这是第一块）"),
        "- 修复完本块后，我会自动继续下一块，直到所有块修复完成。",
        "",
        "## 要求",
        "1. 逐文件、逐处检查并修复【所有】问题，绝不遗漏本块中的任何一处错误。",
        "2. 优先使用 `replace` 做最小改动；不适合局部替换的用 `file` 整体覆盖。",
        "3. 旧片段（replace 的 @@OLD@@）必须能在原文中精确匹配（含缩进与换行）。",
        "4. 完成后简要说明本块改了什么。",
        "",
        "## 输出格式",
        "```replace <相对路径>",
        "@@OLD@@",
        "原来的代码片段（整段精确复制）",
        "@@NEW@@",
        "改成的新代码",
        "```",
        "",
        "或整文件覆盖：",
        "```file <相对路径>",
        "修复后的完整文件内容",
        "```",
        "",
        "## 本块待修复文件",
    ]
    for rel, content in chunk_files:
        lines.append(f"=== FILE: {rel} ===")
        # 超长文件截断展示（防止单文件压垮上下文）
        if len(content) > 50_000:
            lines.append(content[:50_000])
            lines.append("...（文件过长，仅显示前 50000 字符）...")
        else:
            lines.append(content)
        lines.append(f"=== END {rel} ===")
        lines.append("")
    return "\n".join(lines)
