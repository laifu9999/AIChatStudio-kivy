package com.aichatstudio.app.data

import org.json.JSONArray
import org.json.JSONObject

/** 一条聊天消息（JSON 持久化）。 */
data class ChatMessage(
    val role: String,        // user / assistant / system
    val content: String,
    val ts: Long = System.currentTimeMillis(),
) {
    fun toJson(): JSONObject = JSONObject()
        .put("role", role)
        .put("content", content)
        .put("ts", ts)

    companion object {
        fun fromJson(o: JSONObject): ChatMessage = ChatMessage(
            role = o.optString("role", "user"),
            content = o.optString("content", ""),
            ts = o.optLong("ts", System.currentTimeMillis()),
        )
    }
}

/** 会话元信息。 */
data class SessionMeta(
    val id: String,
    val name: String,
    val created: Long,
    val updated: Long,
) {
    fun toJson(): JSONObject = JSONObject()
        .put("id", id)
        .put("name", name)
        .put("created", created)
        .put("updated", updated)

    companion object {
        fun fromJson(o: JSONObject): SessionMeta = SessionMeta(
            id = o.optString("id"),
            name = o.optString("name", "会话"),
            created = o.optLong("created"),
            updated = o.optLong("updated"),
        )
    }
}

/** 一个会话 = 元信息 + 项目文件夹路径 + 消息列表。 */
data class Session(
    val meta: SessionMeta,
    val folder: java.io.File,
    val messages: MutableList<ChatMessage> = mutableListOf(),
) {
    val messagesFile: java.io.File get() = java.io.File(folder, "messages.json")
    val chatMdFile: java.io.File get() = java.io.File(folder, "chat.md")
    val metaFile: java.io.File get() = java.io.File(folder, "meta.json")
}

/** Provider 预设（与桌面版一致）。 */
data class ProviderPreset(
    val name: String,
    val baseUrl: String,
    val protocol: String,          // openai / anthropic
    val freeTier: Boolean = false,
    val defaultModel: String = "",
)

object Providers {
    val LIST = listOf(
        ProviderPreset("OpenAI", "https://api.openai.com/v1", "openai"),
        ProviderPreset("DeepSeek", "https://api.deepseek.com/v1", "openai"),
        ProviderPreset("通义千问(Qwen)", "https://dashscope.aliyuncs.com/compatible-mode/v1", "openai"),
        ProviderPreset("文心一言(ERNIE)", "https://qianfan.baidubce.com/v2", "openai"),
        ProviderPreset("OpenRouter", "https://openrouter.ai/api/v1", "openai"),
        ProviderPreset("Claude(Anthropic)", "https://api.anthropic.com/v1", "anthropic"),
        ProviderPreset("智谱GLM(免费)", "https://open.bigmodel.cn/api/paas/v4", "openai",
            freeTier = true, defaultModel = "glm-4-flash"),
        ProviderPreset("智谱GLM(Flash)", "https://open.bigmodel.cn/api/paas/v4", "openai",
            freeTier = true, defaultModel = "glm-4.7-flash"),
        ProviderPreset("自定义OpenAI兼容", "", "openai"),
    )

    fun byName(name: String): ProviderPreset? = LIST.firstOrNull { it.name == name }
    fun names(): List<String> = LIST.map { it.name }
}
