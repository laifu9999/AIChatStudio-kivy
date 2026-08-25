package com.aichatstudio.app.file

import java.io.File

/**
 * 文件操作层（与桌面版 code_tools/command_exec 语义一致）：
 * - %%FILE:相对路径%% 正文保存标记
 * - file/replace/append/delete/create_dir/savebody 代码块
 * 全部基于 java.io，Android 上对应用目录/授权存储直接可用。
 */
object FileOps {

    data class Op(val op: String, val path: String, val content: String = "",
                  val old: String = "", val new: String = "")

    /** 解析 %%FILE:path%% 标记 → write 操作列表。 */
    fun extractFileMarkers(body: String): List<Op> {
        if (body.isBlank()) return emptyList()
        val ops = mutableListOf<Op>()
        val re = Regex("%%FILE:\\s*(.+?)%%\\s*(.*?)(?=%%FILE:|$)", RegexOption.DOT_MATCHES_ALL)
        for (m in re.findAll(body)) {
            val path = m.groupValues[1].trim().trim('`', '"', '\'')
            var content = m.groupValues[2].trimEnd('\n')
            if (path.isNotEmpty()) ops.add(Op("write", cleanPath(path), content))
        }
        return ops
    }

    /** 去掉 %%FILE:%% 标记（聊天显示层用）。 */
    fun stripFileMarkers(body: String): String {
        if (body.isBlank()) return body
        var t = body.replace(Regex("%%FILE:\\s*(.+?)%%", RegexOption.DOT_MATCHES_ALL), "")
        t = t.replace(Regex("\n{3,}"), "\n\n")
        return t.trim()
    }

    /** 解析 ```file/replace/append/delete/create_dir/savebody 代码块。 */
    fun parseCodeBlocks(text: String): List<Op> {
        val ops = mutableListOf<Op>()
        val re = Regex("```(\\w+)(?:\\s+(?:\"([^\"\\n]+)\"|'([^'\\n]+)'|(\\S+)))?\\s*\\n(.*?)```",
            RegexOption.DOT_MATCHES_ALL)
        for (m in re.findAll(text)) {
            val lang = m.groupValues[1].lowercase()
            val rawPath = (m.groupValues[2].ifEmpty { m.groupValues[3] }.ifEmpty { m.groupValues[4] }).trim()
            val content = m.groupValues[5]
            val path = if (rawPath.isNotEmpty()) cleanPath(rawPath) else extractNameFromContent(content)
            if (path.isEmpty()) continue
            when (lang) {
                "file", "create_file", "write", "new_file", "create", "overwrite", "save", "touch" ->
                    ops.add(Op("write", path, content))
                "append", "concat" -> ops.add(Op("append", path, content))
                "replace", "patch", "edit", "modify" -> {
                    val (old, new) = parseReplace(content)
                    ops.add(Op("replace", path, old = old, new = new))
                }
                "delete", "rm", "remove" -> ops.add(Op("delete", path))
                "create_dir", "mkdir", "make_dir", "folder", "new_folder", "md" ->
                    ops.add(Op("mkdir", path))
                "copy", "cp", "duplicate" -> {
                    val (src, dst) = parseSrcDst(content, path)
                    if (src.isNotEmpty() && dst.isNotEmpty()) ops.add(Op("copy", src, content = dst))
                }
                "move", "mv", "rename", "ren" -> {
                    val (src, dst) = parseSrcDst(content, path)
                    if (src.isNotEmpty() && dst.isNotEmpty()) ops.add(Op("move", src, content = dst))
                }
                "read", "cat", "view" -> ops.add(Op("read", path))
                "list", "ls", "dir" -> ops.add(Op("list", path))
                "savebody", "save_body", "savetext" -> {
                    val spec = if (rawPath.isNotEmpty()) rawPath else content.trim()
                    ops.add(Op("savebody", cleanPath(spec)))
                }
            }
        }
        return ops
    }

    private fun parseReplace(content: String): Pair<String, String> {
        if ("@@OLD@@" in content && "@@NEW@@" in content) {
            return try {
                val old = content.substringAfter("@@OLD@@").substringBefore("@@NEW@@").trim('\n')
                val new = content.substringAfter("@@NEW@@").trim('\n')
                old to new
            } catch (e: Exception) { "" to content }
        }
        if ("->" in content) {
            val parts = content.split("->", limit = 2)
            if (parts.size == 2) return parts[0].trim() to parts[1]
        }
        return "" to content
    }

    /** 从内容中解析源/目标路径（copy/move/rename 用）。 */
    private fun parseSrcDst(content: String, fallbackPath: String): Pair<String, String> {
        val c = content.trim()
        if ("->" in c) {
            val parts = c.split("->", limit = 2)
            if (parts.size == 2) return cleanPath(parts[0]) to cleanPath(parts[1])
        }
        val lines = c.lines().map { it.trim() }.filter { it.isNotEmpty() }
        return when {
            lines.size >= 2 -> cleanPath(lines[0]) to cleanPath(lines[1])
            lines.size == 1 && fallbackPath.isNotEmpty() -> fallbackPath to cleanPath(lines[0])
            else -> fallbackPath to ""
        }
    }

    private fun extractNameFromContent(content: String): String {
        if (content.isBlank()) return ""
        val first = content.trim().lines().firstOrNull()?.trim() ?: return ""
        val m = Regex("^(?:文件名|文件|file|path|路径)\\s*[:：]\\s*(.+)$", RegexOption.IGNORE_CASE)
            .find(first)
        if (m != null) {
            val cand = m.groupValues[1].trim().trim('`', '"', '\'')
            if (looksLikePath(cand)) return cleanPath(cand)
        }
        val m2 = Regex("^[#/*\\s-]*([\\w\\-.\\\\/]+\\.[A-Za-z0-9]+)\\s*$").find(first)
        if (m2 != null) {
            val cand = m2.groupValues[1].trim()
            if (looksLikePath(cand)) return cleanPath(cand)
        }
        return ""
    }

    private fun looksLikePath(s: String): Boolean {
        if (s.isEmpty() || s.length > 260) return false
        if ('.' !in s) return false
        if (' ' in s && '/' !in s && '\\' !in s) return false
        return true
    }

    private fun cleanPath(s: String): String =
        s.trim().trim('`', '"', '\'').replace("[\\[\\]()]".toRegex(), "")

    /** 应用文件操作到 baseDir，返回日志列表。body 供 savebody 使用。 */
    fun applyBlocks(blocks: List<Op>, baseDir: File, body: String = ""): List<String> {
        val logs = mutableListOf<String>()
        for (b in blocks) {
            val rel = b.path.trimStart('/').replace('/', File.separatorChar)
            if (rel.isEmpty()) { logs.add("[!] 跳过：无路径的块"); continue }
            val full = File(baseDir, rel)
            try {
                when (b.op) {
                    "write" -> {
                        full.parentFile?.mkdirs()
                        full.writeText(b.content, Charsets.UTF_8)
                        logs.add("[OK] 写入: $rel (${b.content.length} chars)")
                    }
                    "append" -> {
                        full.parentFile?.mkdirs()
                        full.appendText(b.content, Charsets.UTF_8)
                        logs.add("[追加] 追加: $rel")
                    }
                    "replace" -> {
                        if (!full.exists()) { logs.add("[!] replace: $rel 不存在"); continue }
                        val text = full.readText(Charsets.UTF_8)
                        val newText = if (b.old.isEmpty()) b.new
                        else if (text.contains(b.old)) text.replaceFirst(b.old, b.new)
                        else { logs.add("[!] replace: $rel 找不到 old 片段"); continue }
                        full.writeText(newText, Charsets.UTF_8)
                        logs.add("[替换] 替换: $rel")
                    }
                    "delete" -> {
                        if (full.exists()) {
                            full.deleteRecursively()
                            logs.add("[删] 删除: $rel")
                        } else logs.add("[!] delete: $rel 不存在")
                    }
                    "mkdir" -> {
                        full.mkdirs()
                        logs.add("[目录] 创建目录: $rel")
                    }
                    "savebody" -> {
                        val text = body.trim()
                        if (text.isEmpty()) { logs.add("[!] savebody: 本条消息无正文"); continue }
                        full.parentFile?.mkdirs()
                        full.writeText(text, Charsets.UTF_8)
                        logs.add("[正文] 正文已保存: $rel (${text.length} 字)")
                    }
                    "copy" -> {
                        val dstRel = b.content.trimStart('/').replace('/', File.separatorChar)
                        val dst = File(baseDir, dstRel)
                        if (!full.exists()) { logs.add("[!] copy: $rel 不存在"); continue }
                        dst.parentFile?.mkdirs()
                        if (full.isDirectory) full.copyRecursively(dst, overwrite = true)
                        else full.copyTo(dst, overwrite = true)
                        logs.add("[复制] $rel -> $dstRel")
                    }
                    "move" -> {
                        val dstRel = b.content.trimStart('/').replace('/', File.separatorChar)
                        val dst = File(baseDir, dstRel)
                        if (!full.exists()) { logs.add("[!] move: $rel 不存在"); continue }
                        dst.parentFile?.mkdirs()
                        val ok = full.renameTo(dst)
                        if (!ok) {
                            if (full.isDirectory) full.copyRecursively(dst, overwrite = true)
                            else full.copyTo(dst, overwrite = true)
                            full.deleteRecursively()
                        }
                        logs.add("[移动] $rel -> $dstRel")
                    }
                    "read" -> {
                        if (!full.exists()) { logs.add("[!] read: $rel 不存在"); continue }
                        val text = try {
                            full.readText(Charsets.UTF_8)
                        } catch (_: Exception) { full.readText(java.nio.charset.Charset.forName("GBK")) }
                        logs.add("[读取] $rel：\n${text.take(2000)}")
                    }
                    "list" -> {
                        val dir = if (full.isDirectory) full else full.parentFile ?: baseDir
                        val items = dir.listFiles()?.sortedBy { it.name } ?: emptyList()
                        logs.add("[列出] $rel：\n" + items.joinToString("\n") {
                            (if (it.isDirectory) "[D] " else "[F] ") + it.name
                        })
                    }
                    else -> logs.add("[!] 未知操作: ${b.op}")
                }
            } catch (e: Exception) {
                logs.add("[失败] ${b.op} $rel: ${e.message}")
            }
        }
        return logs
    }
}
