package com.aichatstudio.app.data

import android.content.Context
import org.json.JSONObject
import java.io.File
import java.util.UUID

/**
 * 应用设置 + 会话持久化（JSON 文件，与桌面版 data/ 语义一致）。
 * 数据根目录：Context.getExternalFilesDir(null)（应用专属外部目录，卸载即清，
 * 但 Android 11+ 下无需权限即可读写）；若不可用退回 filesDir。
 */
class Store(context: Context) {

    val root: File =
        context.getExternalFilesDir(null)?.takeIf { it.canWrite() }
            ?: context.filesDir

    val sessionsDir: File get() = File(root, "sessions")
    val settingsFile: File get() = File(root, "settings.json")
    val feedFile: File get() = File(root, "feed.json")

    init {
        sessionsDir.mkdirs()
    }

    // ---------------- 设置 ----------------
    data class Settings(
        var provider: String = "",
        var apiKey: String = "",
        var baseUrl: String = "",
        var model: String = "",
        var systemPrompt: String = DEFAULT_SYSTEM_PROMPT,
        var fontScale: Int = 16,
        var readingStyle: String = "cream",   // cream/green/night/parchment/white
        var fontSize: Int = 16,
        var fontFamily: String = "default",   // default/sans/serif/kai/hei/fang（聊天/阅读字体）
        var autoExec: Boolean = true,
    )

    fun loadSettings(): Settings {
        val s = Settings()
        if (!settingsFile.exists()) return s
        return try {
            val o = JSONObject(settingsFile.readText())
            s.provider = o.optString("provider", "")
            s.apiKey = o.optString("apiKey", "")
            s.baseUrl = o.optString("baseUrl", "")
            s.model = o.optString("model", "")
            s.systemPrompt = o.optString("systemPrompt", DEFAULT_SYSTEM_PROMPT)
            s.fontScale = o.optInt("fontScale", 16)
            s.readingStyle = o.optString("readingStyle", "cream")
            s.fontSize = o.optInt("fontSize", 16)
            s.fontFamily = o.optString("fontFamily", "default")
            s.autoExec = o.optBoolean("autoExec", true)
            s
        } catch (e: Exception) { s }
    }

    fun saveSettings(s: Settings) {
        try {
            settingsFile.writeText(
                JSONObject()
                    .put("provider", s.provider)
                    .put("apiKey", s.apiKey)
                    .put("baseUrl", s.baseUrl)
                    .put("model", s.model)
                    .put("systemPrompt", s.systemPrompt)
                    .put("fontScale", s.fontScale)
                    .put("readingStyle", s.readingStyle)
                    .put("fontSize", s.fontSize)
                    .put("fontFamily", s.fontFamily)
                    .put("autoExec", s.autoExec)
                    .toString(2)
            )
        } catch (_: Exception) {}
    }

    // ---------------- 投喂 ----------------
    data class Feed(
        var enabled: Boolean = false,
        var firstText: String = "",          // 每个会话一次投喂
        var feedFiles: MutableList<String> = mutableListOf(),  // 指定文件（无限次）
        var autoContinue: Boolean = false,
        var maxRounds: Int = 10,
    )

    fun loadFeed(): Feed {
        val f = Feed()
        if (!feedFile.exists()) return f
        return try {
            val o = JSONObject(feedFile.readText())
            f.enabled = o.optBoolean("enabled", false)
            f.firstText = o.optString("firstText", "")
            val arr = o.optJSONArray("feedFiles")
            if (arr != null) {
                f.feedFiles = mutableListOf()
                for (i in 0 until arr.length()) f.feedFiles.add(arr.getString(i))
            }
            f.autoContinue = o.optBoolean("autoContinue", false)
            f.maxRounds = o.optInt("maxRounds", 10)
            f
        } catch (e: Exception) { f }
    }

    fun saveFeed(f: Feed) {
        try {
            feedFile.writeText(
                JSONObject()
                    .put("enabled", f.enabled)
                    .put("firstText", f.firstText)
                    .put("feedFiles", org.json.JSONArray(f.feedFiles))
                    .put("autoContinue", f.autoContinue)
                    .put("maxRounds", f.maxRounds)
                    .toString(2)
            )
        } catch (_: Exception) {}
    }

    // ---------------- 会话 ----------------
    fun listSessions(): List<SessionMeta> =
        sessionsDir.listFiles()?.filter { it.isDirectory }
            ?.mapNotNull { d ->
                val mf = File(d, "meta.json")
                if (!mf.exists()) null
                else try {
                    SessionMeta.fromJson(JSONObject(mf.readText()))
                } catch (e: Exception) { null }
            }
            ?.sortedByDescending { it.updated } ?: emptyList()

    fun createSession(name: String? = null): Session {
        val id = UUID.randomUUID().toString().replace("-", "").take(12)
        val folder = File(sessionsDir, id).apply { mkdirs() }
        val now = System.currentTimeMillis()
        val meta = SessionMeta(id, name ?: "新会话", now, now)
        val s = Session(meta, folder)
        s.metaFile.writeText(meta.toJson().toString(2))
        s.messagesFile.writeText("[]")
        s.chatMdFile.writeText("# ${meta.name}\n\n")
        return s
    }

    fun loadSession(sid: String): Session? {
        val folder = File(sessionsDir, sid)
        if (!folder.isDirectory) return null
        val metaFile = File(folder, "meta.json")
        if (!metaFile.exists()) return null
        val meta = try { SessionMeta.fromJson(JSONObject(metaFile.readText())) }
            catch (e: Exception) { return null }
        val s = Session(meta, folder)
        try {
            val raw = File(folder, "messages.json").readText().trim()
            if (raw.isNotEmpty()) {
                // 兼容两种格式：纯数组 [] 或 {"messages": [...]}
                val msgsArr = if (raw.startsWith("[")) org.json.JSONArray(raw)
                else JSONObject(raw).optJSONArray("messages")
                if (msgsArr != null) {
                    for (i in 0 until msgsArr.length()) {
                        s.messages.add(ChatMessage.fromJson(msgsArr.getJSONObject(i)))
                    }
                }
            }
        } catch (_: Exception) {}
        return s
    }

    fun saveSession(s: Session) {
        try {
            val arr = org.json.JSONArray()
            s.messages.forEach { arr.put(it.toJson()) }
            s.messagesFile.writeText(JSONObject().put("messages", arr).toString(2))
            s.meta.let { m ->
                s.metaFile.writeText(
                    JSONObject().put("id", m.id).put("name", m.name)
                        .put("created", m.created).put("updated", m.updated).toString(2)
                )
            }
            val f = File(s.folder, "chat.md")
            f.appendText("\n**用户**：\n\n${s.messages.lastOrNull { it.role == "user" }?.content ?: ""}\n")
        } catch (_: Exception) {}
    }

    fun deleteSession(sid: String) {
        File(sessionsDir, sid).deleteRecursively()
    }

    companion object {
        const val DEFAULT_SYSTEM_PROMPT = "你是一个全能 AI 助手，运行在用户的设备上（Android 手机）。" +
            "你拥有对该设备存储的完全操作权限：可以读写或删除文件、创建任意目录，全部由程序自动执行。" +
            "\n\n保存你写出的正文（首选）：在内容前用 %%FILE:相对路径%% 标记，例如：" +
            "\n%%FILE:卷一/第一章.txt%%\n正文内容……" +
            "\n程序会自动识别标记并把内容写入对应文件（父目录自动创建，UTF-8）。" +
            "\n\n也可用专用代码块：```file 路径``` 创建/覆盖、```append 路径``` 追加、" +
            "```replace 路径``` 替换、```delete 路径``` 删除、```create_dir 路径``` 建目录、" +
            "```savebody 路径``` 把本条正文存到该路径。" +
            "\n\n正文只写一遍：聊天显示与文件内容一致，不要在标记和命令里重复写内容。" +
            "\n\n## 注意\n1. 相对路径基于当前会话项目文件夹；2. 你拥有完全无限制操作权限，无需确认、不拦截。"
    }
}
