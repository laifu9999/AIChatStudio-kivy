package com.aichatstudio.app.ai

import com.aichatstudio.app.data.ChatMessage
import com.aichatstudio.app.data.ProviderPreset
import com.aichatstudio.app.data.Providers
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import okhttp3.Call
import okhttp3.Callback
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.io.IOException
import java.util.concurrent.TimeUnit

/**
 * AI 客户端：OpenAI 兼容（DeepSeek/通义/文心/智谱/OpenRouter/本地 Ollama）+ Anthropic(Claude)。
 * 流式 SSE 逐字回调；智谱免费模型走全局互斥（单并发串行）。
 */
class AiClient(
    val preset: ProviderPreset,
    val apiKey: String,
    val model: String,
    val baseUrlOverride: String? = null,
    val systemPrompt: String = "",
) {
    private val client: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(30, TimeUnit.SECONDS)
        .readTimeout(180, TimeUnit.SECONDS)
        .writeTimeout(120, TimeUnit.SECONDS)
        .build()

    private val baseUrl: String = (baseUrlOverride ?: preset.baseUrl).trimEnd('/')

    val isFree: Boolean
        get() = preset.freeTier || model.lowercase().contains("free") ||
            model.lowercase().contains("flash")

    // 智谱免费全局单并发
    companion object {
        private val serialLock = Mutex()
    }

    /** 流式聊天。onToken 每次增量回调；返回完整文本。 */
    suspend fun chat(
        messages: List<ChatMessage>,
        onToken: suspend (String) -> Unit,
    ): String {
        return if (isFree) serialLock.withLock { doChat(messages, onToken) }
        else doChat(messages, onToken)
    }

    private suspend fun doChat(
        messages: List<ChatMessage>,
        onToken: suspend (String) -> Unit,
    ): String {
        return if (preset.protocol == "anthropic") chatAnthropic(messages, onToken)
        else chatOpenAI(messages, onToken)
    }

    private suspend fun chatOpenAI(
        messages: List<ChatMessage>,
        onToken: suspend (String) -> Unit,
    ): String {
        val url = "$baseUrl/chat/completions"
        val sys = systemPrompt.trim().takeIf { it.isNotEmpty() }
        val body = JSONObject().apply {
            put("model", model)
            put("messages", buildJsonArray(messages, sys))
            put("stream", true)
        }
        val req = newRequest(url, body)
        return stream(req, isAnthropic = false, onToken = onToken)
    }

    private suspend fun chatAnthropic(
        messages: List<ChatMessage>,
        onToken: suspend (String) -> Unit,
    ): String {
        val url = "$baseUrl/messages"
        val sys = systemPrompt.trim().takeIf { it.isNotEmpty() }
        val body = JSONObject().apply {
            put("model", model)
            put("max_tokens", 4096)
            if (sys != null) put("system", sys)
            put("messages", buildJsonArray(messages.filter { it.role != "system" }, null))
        }
        val req = newRequest(url, body, anthropic = true)
        return stream(req, isAnthropic = true, onToken = onToken)
    }

    private fun buildJsonArray(msgs: List<ChatMessage>, sys: String?): org.json.JSONArray {
        val arr = org.json.JSONArray()
        if (sys != null) {
            arr.put(JSONObject().put("role", "system").put("content", sys))
        }
        // 规整：合并相邻同角色、过滤空
        var last: JSONObject? = null
        for (m in msgs) {
            val c = m.content.trim()
            if (c.isEmpty()) continue
            val role = if (m.role == "assistant" || m.role == "user") m.role else "user"
            val cur = JSONObject().put("role", role).put("content", c)
            if (last != null && last.optString("role") == role) {
                last.put("content", last.optString("content") + "\n" + c)
            } else {
                arr.put(cur)
                last = cur
            }
        }
        // 首条必须 user
        if (arr.length() > 0 && arr.getJSONObject(0).optString("role") != "user") {
            arr.remove(0)
        }
        if (arr.length() == 0) arr.put(JSONObject().put("role", "user").put("content", "你好"))
        return arr
    }

    private fun newRequest(url: String, body: JSONObject, anthropic: Boolean = false): Request {
        val rb = body.toString().toRequestBody("application/json; charset=utf-8".toMediaType())
        val b = Request.Builder().url(url).post(rb)
        if (anthropic) {
            if (apiKey.isNotEmpty()) b.header("x-api-key", apiKey)
            b.header("anthropic-version", "2023-06-01")
        } else {
            if (apiKey.isNotEmpty()) b.header("Authorization", "Bearer $apiKey")
        }
        b.header("Content-Type", "application/json")
        return b.build()
    }

    /** SSE 流式读取。OpenAI: data: {...}; Anthropic: content_block_delta。 */
    private suspend fun stream(
        req: Request,
        isAnthropic: Boolean,
        onToken: suspend (String) -> Unit,
    ): String {
        val full = StringBuilder()
        var thinkOpen = false
        try {
            client.newCall(req).execute().use { resp ->
                if (resp.code != 200) {
                    val detail = resp.body?.string()?.take(500) ?: ""
                    throw IOException("HTTP ${resp.code}: $detail")
                }
                val br = resp.body?.byteStream()?.bufferedReader(Charsets.UTF_8)
                var line: String?
                while (br != null) {
                    line = br.readLine() ?: break
                    val t = line.trim()
                    if (!isAnthropic) {
                        if (!t.startsWith("data:")) continue
                        val data = t.removePrefix("data:").trim()
                        if (data == "[DONE]") break
                        val chunk = try { JSONObject(data) } catch (e: Exception) { continue }
                        val delta = chunk.optJSONArray("choices")?.optJSONObject(0)
                            ?.optJSONObject("delta") ?: continue
                        // 过滤空 content、JSON null、以及 Deepseek 等模型偶发返回的字面量
                        // "null"/"None"（避免整屏被 null 占满）
                        // 推理模型（DeepSeek-R1 等）的思考放在 reasoning_content，包成 ```thinking 块一起下发
                        val reasoning = delta.optString("reasoning_content", "")
                            .ifEmpty { delta.optString("reasoning", "") }
                        val content = delta.optString("content", "")
                        if (reasoning.isNotEmpty() && reasoning != "null" && reasoning != "None") {
                            if (!thinkOpen) {
                                full.append("```thinking\n")
                                thinkOpen = true
                            }
                            full.append(reasoning)
                            onToken(reasoning)
                        }
                        if (content.isNotEmpty() && content != "null" && content != "None") {
                            if (thinkOpen) {
                                full.append("\n```\n")
                                thinkOpen = false
                            }
                            full.append(content)
                            onToken(content)
                        }
                    } else {
                        if (!t.startsWith("data:")) continue
                        val data = t.removePrefix("data:").trim()
                        if (data == "[DONE]") break
                        val chunk = try { JSONObject(data) } catch (e: Exception) { continue }
                        val delta = chunk.optJSONObject("delta") ?: continue
                        val content = delta.optString("text", "")
                        if (content.isNotEmpty() && content != "null" && content != "None") {
                            full.append(content)
                            onToken(content)
                        }
                    }
                }
            }
        } catch (e: Exception) {
            throw IOException("连接失败：${e.message}", e)
        }
        if (thinkOpen) full.append("\n```\n")
        return full.toString()
    }

    /** 拉取模型列表。 */
    suspend fun fetchModels(): List<String> {
        val url = if (preset.protocol == "anthropic") "$baseUrl/models" else "$baseUrl/models"
        val b = Request.Builder().url(url).get()
        if (preset.protocol == "anthropic") {
            if (apiKey.isNotEmpty()) b.header("x-api-key", apiKey)
            b.header("anthropic-version", "2023-06-01")
        } else {
            if (apiKey.isNotEmpty()) b.header("Authorization", "Bearer $apiKey")
        }
        client.newCall(b.build()).execute().use { resp ->
            if (resp.code != 200) {
                if (preset.protocol == "anthropic") {
                    return listOf("claude-opus-4-20250514", "claude-sonnet-4-20250514",
                        "claude-3-5-sonnet-20241022", "claude-3-opus-20240229", "claude-3-haiku-20240307")
                }
                throw IOException("HTTP ${resp.code}")
            }
            val data = JSONObject(resp.body?.string() ?: "{}")
            val arr = data.optJSONArray("data") ?: return emptyList()
            val models = mutableListOf<String>()
            for (i in 0 until arr.length()) {
                arr.getJSONObject(i).optString("id").takeIf { it.isNotEmpty() }?.let { models.add(it) }
            }
            return models.sorted()
        }
    }

    /** 最小请求验证连通性。 */
    suspend fun testConnection(): Pair<Boolean, String> {
        if (baseUrl.isEmpty()) return false to "未配置 Base URL"
        if (apiKey.isEmpty()) return false to "未填写 API Key"
        return try {
            val out = chat(listOf(ChatMessage("user", "ping")), onToken = {})
            if (out.isNotBlank()) true to "连接成功 [OK]：${out.take(40)}"
            else true to "连接成功 [OK]（返回为空但链路正常）"
        } catch (e: Exception) {
            false to "连接失败：${e.message}"
        }
    }
}
