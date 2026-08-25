package com.aichatstudio.app.ui

import android.app.Application
import android.content.ClipboardManager
import android.content.Context
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.aichatstudio.app.ai.AiClient
import com.aichatstudio.app.data.ChatMessage
import com.aichatstudio.app.data.Providers
import com.aichatstudio.app.data.Session
import com.aichatstudio.app.data.Store
import com.aichatstudio.app.file.FileOps
import com.aichatstudio.app.phone.PhoneOps
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File
import kotlin.random.Random

/** 全局状态 + 聊天/AI/投喂/续章/文件 逻辑。 */
class AppState(app: Application) : AndroidViewModel(app) {

    val store = Store(app)
    var settings by mutableStateOf(store.loadSettings())
    var feed by mutableStateOf(store.loadFeed())

    var sessions by mutableStateOf(store.listSessions())
        private set
    var current by mutableStateOf<Session?>(null)
        private set

    // 聊天界面状态
    var messages by mutableStateOf<List<ChatMessage>>(emptyList())
        private set
    var feedStatus by mutableStateOf("")
        private set
    var streaming by mutableStateOf(false)
        private set
    var inputText by mutableStateOf("")

    // 续章状态
    private var autoRound = 0
    private var autoTotal = 0
    private var autoActive = false
    private var stopFlag = false
    private var autoToken = 0

    private var client: AiClient? = null

    companion object {
        // 始终追加到 systemPrompt：强制让 AI 用标记保存文件，不要说"做不到"
        private const val CAPS_SUFFIX = "\n\n[设备能力 - 必须遵守]\n" +
            "你【可以】直接保存文件到用户手机存储。保存任何内容时，必须在正文前用 %%FILE:相对路径%% 标记，" +
            "或用 ```file 路径\\n正文``` 代码块。程序会自动创建目录并写入到设备（UTF-8）。\n" +
            "也可用 ```copy/move/rename/read/list/create_dir/append/replace/delete/open_url``` 等代码块操作文件和打开网页。\n" +
            "【严禁】回复「无法保存/做不到/建议复制到其他App」等话术 —— 你的输出会被自动执行，写入设备。" +
            "用户要求保存时，直接输出文件内容并带上标记即可。\n\n" +
            "[保存规范 - 用户要求保存时严格执行]\n" +
            "1) 按用户说的「分类/类别」建文件夹：用 ```create_dir 分类名``` 先建目录。\n" +
            "2) 每一篇/每一类用【单独文件】保存：在每段正文前加 %%FILE:分类/命名.ext%% 标记（ext 为 .txt/.md）。\n" +
            "3) 文件命名要符合内容：不要用通用名如 new1.txt；用故事名/章节名/主题名。\n" +
            "4) 正文【只在标记后出现一次】，不要在标记前/后/教程里重复写内容。\n" +
            "5) 【严禁】给「打开记事本→粘贴→另存为」这类手把手保存步骤；【严禁】说「我无法保存」。\n" +
            "6) 保存完后回复一句「已保存到：路径」即可，不要再贴正文。\n" +
            "7) 文件可在 App「阅读」→「项目文件」里直接打开查看。"

        // 当用户消息含保存意图时，本轮追加的强化指令（recency 提示）
        private const val SAVE_NUDGE = "【本次要求保存文件】" +
            "你必须立即执行：\n" +
            "① 如果是分类/分篇保存，先用 ```create_dir 分类名``` 建目录；\n" +
            "② 为每一篇/每一类用 %%FILE:分类/命名.ext%% 标记（命名贴合内容，不要用 1.txt 这种）；\n" +
            "③ 正文【只在标记之后写一遍】，写完即结束；\n" +
            "④ 【绝对不要】回复「我无法保存/打开记事本粘贴」之类的话，标记里的内容会被程序自动写入设备。"

        // 流式显示时，去掉 ```thinking ... ``` 思考块（UI 端也会剥，这里给后端兜底）
        private val THINKING_RE = Regex("```thinking\\s*\\n(.*?)```", RegexOption.DOT_MATCHES_ALL)
        fun stripThinking(content: String): String =
            content.replace(THINKING_RE, "").trim()

        // 检测用户是否要求保存/创建文件
        fun looksLikeSaveRequest(text: String): Boolean {
            val t = text.lowercase()
            val keys = listOf(
                "保存", "存到", "存入", "写入", "写进", "写到", "建文件", "创建文件", "创立文件",
                "建文件夹", "创建文件夹", "创立文件夹", "建目录", "创建目录", "建个文件",
                "分类保存", "分类存", "单独文件", "生成文件", "存为", "另存为", "写到文件",
                "save", "create file", "create folder", "create directory", "mkdir", "make folder",
                "make directory", "write to file", "write file", "store to", "save as"
            )
            return keys.any { t.contains(it) }
        }
    }

    fun rebuildClient() {
        client = if (settings.provider.isEmpty()) null else {
            val preset = Providers.byName(settings.provider) ?: return
            AiClient(
                preset = preset,
                apiKey = settings.apiKey,
                model = settings.model,
                baseUrlOverride = settings.baseUrl.takeIf { it.isNotBlank() },
                systemPrompt = settings.systemPrompt + CAPS_SUFFIX +
                    if (settings.deepThinking) {
                        "\n\n[深度思考已开启] 请在最终回答前先进行充分推理，并把推理过程放在 ```thinking 与 ``` 之间。"
                    } else "",
            )
        }
    }

    init { rebuildClient() }

    // ---------------- 会话 ----------------
    fun newSession() {
        val s = store.createSession()
        sessions = store.listSessions()
        selectSession(s.meta.id)
    }

    fun selectSession(sid: String) {
        current = store.loadSession(sid)
        messages = current?.messages?.toList() ?: emptyList()
        autoActive = false
        feedStatus = ""
    }

    fun deleteSession(sid: String) {
        store.deleteSession(sid)
        sessions = store.listSessions()
        if (current?.meta?.id == sid) {
            current = null; messages = emptyList()
        }
    }

    fun saveSettings() {
        store.saveSettings(settings)
        rebuildClient()
    }

    fun saveFeed() {
        store.saveFeed(feed)
    }

    // ---------------- 投喂 ----------------
    // 首次投喂也每次都带，不再做"每个会话一次"的去重
    private fun buildFeedContext(): Pair<String, Boolean> {
        if (!feed.enabled) return "" to false
        val parts = mutableListOf<String>()
        if (feed.firstText.isNotBlank()) {
            parts.add(feed.firstText)
        }
        for (p in feed.feedFiles) {
            val f = File(p)
            if (f.exists() && f.isFile) {
                val content = try { f.readText(Charsets.UTF_8) } catch (e: Exception) { "" }
                if (content.isNotBlank()) parts.add("[文件:${f.name}]\n$content")
            }
        }
        if (parts.isEmpty()) return "" to false
        return parts.joinToString("\n\n") to true
    }

    // ---------------- 聊天 ----------------
    fun send(text: String) {
        val t = text.trim()
        if (t.isEmpty() || streaming) return
        if (current == null) newSession()
        inputText = ""
        autoToken++
        val s = current ?: return

        val feedCfg = feed
        autoActive = feedCfg.autoContinue
        autoRound = 1
        autoTotal = if (autoActive) feedCfg.maxRounds.coerceIn(1, 300) else 1
        if (autoActive) feedStatus = "自动续章已开启：共 $autoTotal 章"

        s.messages.add(ChatMessage("user", t))
        current = s
        messages = s.messages.toList()
        store.saveSession(s)
        runChat(t, auto = autoActive)
    }

    fun stop() {
        stopFlag = true
        autoActive = false
        streaming = false
        feedStatus = "已停止"
    }

    private fun runChat(userText: String, auto: Boolean) {
        val s = current ?: return
        val c = client
        if (c == null) {
            s.messages.add(ChatMessage("assistant", "尚未配置 AI。请点右上角「设置」填写提供商 API Key 与模型。"))
            current = s; messages = s.messages.toList()
            return
        }
        streaming = true
        stopFlag = false
        feedStatus = buildFeedContext().let { (ctx, has) ->
            if (has) "投喂已注入" else if (feed.enabled) "投喂：无内容" else feedStatus
        }
        viewModelScope.launch {
            val holder = mutableListOf<ChatMessage>()
            holder.addAll(s.messages.filter { it.role != "system" })
            val (ctx, _) = buildFeedContext()
            val msgs = if (ctx.isNotBlank()) {
                mutableListOf(ChatMessage("system", ctx)).apply { addAll(holder) }
            } else holder
            // 检测到保存意图：在请求末尾追加强化指令（不写入会话历史）
            if (looksLikeSaveRequest(userText)) {
                msgs.add(ChatMessage("system", SAVE_NUDGE))
            }
            val streamBubble = ChatMessage("assistant", "")
            s.messages.add(streamBubble)
            current = s; messages = s.messages.toList()

            val buffer = StringBuilder()
            var full = ""
            val showThink = settings.showThinking
            // 客户端打字机：showThink=true 时整段流；否则跳过 ```thinking``` 块只流式显示最终答案
            val typingJob = viewModelScope.launch(Dispatchers.Main) {
                var shown = 0
                var streamStart = 0
                var inThinkPhase = false
                while (streaming) {
                    val target = synchronized(buffer) { buffer.toString() }
                    if (showThink) {
                        streamStart = 0
                    } else {
                        val m = THINKING_RE.find(target)
                        if (m != null) {
                            val newStart = m.range.last + 1
                            if (streamStart != newStart) {
                                streamStart = newStart
                                shown = 0
                            }
                        } else if (target.contains("```thinking")) {
                            // 思考块还没写完：只显示"思考中"
                            if (!inThinkPhase) {
                                inThinkPhase = true
                                streamBubble.content = "思考中…"
                                messages = s.messages.toList()
                            }
                            kotlinx.coroutines.delay(28); continue
                        } else {
                            streamStart = 0
                        }
                    }
                    inThinkPhase = false
                    val displayable = target.substring(streamStart)
                    if (shown < displayable.length) {
                        val gap = displayable.length - shown
                        val step = when {
                            gap > 200 -> 6
                            gap > 80 -> 4
                            gap > 20 -> 2
                            else -> 1
                        }
                        shown = (shown + step).coerceAtMost(displayable.length)
                        streamBubble.content = displayable.substring(0, shown) + "▌"
                        messages = s.messages.toList()
                    }
                    kotlinx.coroutines.delay(28)
                }
            }
            try {
                full = withContext(Dispatchers.IO) {
                    c.chat(msgs) { delta ->
                        // 只往 buffer 里追加，由前台打字机协程负责显示
                        synchronized(buffer) { buffer.append(delta) }
                    }
                }
            } catch (e: Exception) {
                full = "[!] 调用出错：${e.message}"
                synchronized(buffer) { buffer.setLength(0); buffer.append(full) }
            }
            streaming = false
            typingJob.join()
            streamBubble.content = stripThinking(full)
            if (full.startsWith("[!]") || full.isBlank()) {
                // 出错时保留错误气泡
            } else if (settings.autoExec) {
                // 自动执行文件/命令操作（用原始 full 确保能扫到标记）
                applyFileOps(full)
            }
            val stored = stripThinking(full)
            s.messages.remove(streamBubble)
            s.messages.add(ChatMessage("assistant", stored))
            current = s; messages = s.messages.toList()
            store.saveSession(s)
            streaming = false

            if (!stopFlag && auto) maybeAutoContinue()
        }
    }

    /** 自动续章：随机 3~6 秒后继续下一章。 */
    private suspend fun maybeAutoContinue() {
        if (!autoActive || stopFlag) return
        if (autoRound >= autoTotal) {
            autoActive = false
            feedStatus = "续章完成：共 $autoTotal 章"
            return
        }
        val wait = Random.nextDouble(3.0, 6.0)
        feedStatus = "续章中 第 ${autoRound + 1}/$autoTotal 章，等待 ${"%.1f".format(wait)} 秒…"
        val tok = autoToken
        delay((wait * 1000).toLong())
        if (tok != autoToken || stopFlag || !autoActive) return
        autoRound++
        val s = current ?: return
        val cont = "（自动续章）请继续创作第 $autoRound 章，保持文风与剧情连贯。"
        s.messages.add(ChatMessage("user", cont))
        current = s; messages = s.messages.toList()
        store.saveSession(s)
        runChat(cont, auto = true)
    }

    /** 自动应用 AI 回复里的 %%FILE: 标记和代码块。 */
    private fun applyFileOps(reply: String) {
        val folder = current?.folder ?: return
        try {
            val markers = FileOps.extractFileMarkers(reply)
            if (markers.isNotEmpty()) {
                val logs = FileOps.applyBlocks(markers, folder)
                feedStatus = "[文件] 已自动保存：${logs.size} 项"
                current?.messages?.add(ChatMessage("assistant",
                    "[文件] 已自动保存：\n" + logs.joinToString("\n")))
            }
            val blocks = FileOps.parseCodeBlocks(reply)
            if (blocks.isNotEmpty()) {
                val logs = FileOps.applyBlocks(blocks, folder, body = reply)
                feedStatus = "[执行] 已自动应用：${logs.size} 项"
                current?.messages?.add(ChatMessage("assistant",
                    "[执行] 文件操作：\n" + logs.joinToString("\n")))
            }
            val opened = PhoneOps.parseOpenUrls(getApplication<Application>(), reply)
            if (opened.isNotEmpty()) {
                feedStatus = "[手机] 已打开网页：${opened.size} 个"
                current?.messages?.add(ChatMessage("assistant",
                    "[手机] 已打开：\n" + opened.joinToString("\n")))
                current?.let { store.saveSession(it) }
            }
        } catch (e: Exception) {
            feedStatus = "自动执行出错：${e.message}"
        }
    }

    // ---------------- 剪贴板 ----------------
    fun pasteText(): String {
        return try {
            val cm = getApplication<Application>().getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
            cm.primaryClip?.getItemAt(0)?.text?.toString() ?: ""
        } catch (e: Exception) { "" }
    }

    fun copyText(t: String) {
        try {
            val cm = getApplication<Application>().getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
            cm.setPrimaryClip(android.content.ClipData.newPlainText("text", t))
        } catch (_: Exception) {}
    }

    // ---------------- 工具 ----------------
    /** 列出会话项目文件夹里的文件。 */
    fun listProjectFiles(): List<Pair<String, File>> {
        val folder = current?.folder ?: return emptyList()
        val out = mutableListOf<Pair<String, File>>()
        folder.walkTopDown().forEach { f ->
            if (f.isFile && f.name !in setOf("messages.json", "chat.md", "meta.json")) {
                out.add(f.relativeTo(folder).path to f)
            }
        }
        return out.sortedBy { it.first }
    }

    fun listDir(dir: File): List<Pair<String, File>> =
        dir.listFiles()?.sortedBy { it.name }?.map { it.name to it } ?: emptyList()
}
