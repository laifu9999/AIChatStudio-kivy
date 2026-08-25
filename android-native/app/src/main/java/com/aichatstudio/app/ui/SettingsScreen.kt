package com.aichatstudio.app.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.aichatstudio.app.ai.AiClient
import com.aichatstudio.app.data.Providers
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(state: AppState, onBack: () -> Unit) {
    val pal = Styles.palette(state.settings.readingStyle)
    val scope = rememberCoroutineScope()
    var status by remember { mutableStateOf("") }
    var modelOptions by remember { mutableStateOf(listOf<String>()) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(pal.bg)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .background(pal.panel)
                .padding(8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            TextButton(onClick = onBack) { Text("← 返回", color = pal.text) }
            Text("设置", color = pal.text, fontSize = 17.sp, fontWeight = FontWeight.Bold)
        }

        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(14.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            // 提供商（可点击下拉）
            var providerMenu by remember { mutableStateOf(false) }
            Box {
                OutlinedButton(onClick = { providerMenu = true }, modifier = Modifier.fillMaxWidth()) {
                    Text("提供商：${state.settings.provider.ifEmpty { "选择" }}", fontSize = 14.sp)
                }
                DropdownMenu(expanded = providerMenu, onDismissRequest = { providerMenu = false }) {
                    Providers.names().forEach { name ->
                        DropdownMenuItem(text = { Text(name) }, onClick = {
                            state.settings = state.settings.copy(provider = name)
                            val p = Providers.byName(name)
                            if (p != null) {
                                state.settings = state.settings.copy(
                                    baseUrl = p.baseUrl,
                                    model = p.defaultModel,
                                )
                                modelOptions = listOf(p.defaultModel).filter { it.isNotEmpty() }
                            }
                            providerMenu = false
                        })
                    }
                }
            }

            // API Key + 粘贴
            Row(verticalAlignment = Alignment.CenterVertically) {
                OutlinedTextField(
                    value = state.settings.apiKey,
                    onValueChange = { state.settings = state.settings.copy(apiKey = it) },
                    label = { Text("API Key") },
                    singleLine = true,
                    modifier = Modifier.weight(1f),
                )
                Spacer(Modifier.width(6.dp))
                Button(onClick = {
                    val t = state.pasteText()
                    if (t.isNotEmpty()) {
                        state.settings = state.settings.copy(apiKey = t)
                        status = "已粘贴"
                    } else status = "剪贴板为空"
                }) { Text("粘贴", fontSize = 13.sp) }
            }

            // Base URL
            OutlinedTextField(
                value = state.settings.baseUrl,
                onValueChange = { state.settings = state.settings.copy(baseUrl = it) },
                label = { Text("Base URL（留空用默认）") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )

            // 模型
            OutlinedTextField(
                value = state.settings.model,
                onValueChange = { state.settings = state.settings.copy(model = it) },
                label = { Text("模型") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            // 获取模型列表
            Button(onClick = {
                scope.launch {
                    status = "正在获取模型列表…"
                    try {
                        val p = Providers.byName(state.settings.provider)
                        if (p == null) { status = "请先选择提供商"; return@launch }
                        val c = AiClient(p, state.settings.apiKey, state.settings.model,
                            state.settings.baseUrl.takeIf { it.isNotBlank() })
                        val models = withContext(Dispatchers.IO) { c.fetchModels() }
                        modelOptions = models
                        if (models.isNotEmpty()) {
                            state.settings = state.settings.copy(model = models.first())
                        }
                        status = "已获取 ${models.size} 个模型"
                    } catch (e: Exception) { status = "获取失败：${e.message}" }
                }
            }) { Text("获取模型列表", fontSize = 14.sp) }

            // 测试连接
            Button(onClick = {
                scope.launch {
                    status = "正在测试连接…"
                    val p = Providers.byName(state.settings.provider)
                    if (p == null) { status = "请先选择提供商"; return@launch }
                    val c = AiClient(p, state.settings.apiKey, state.settings.model,
                        state.settings.baseUrl.takeIf { it.isNotBlank() },
                        state.settings.systemPrompt)
                    val (ok, msg) = withContext(Dispatchers.IO) { c.testConnection() }
                    status = (if (ok) "[OK] " else "[X] ") + msg
                }
            }) { Text("测试连接", fontSize = 14.sp) }

            if (status.isNotEmpty()) {
                Text(status, color = pal.textDim, fontSize = 13.sp)
            }

            HorizontalDivider()

            // 阅读风格
            var styleMenu by remember { mutableStateOf(false) }
            Box {
                OutlinedButton(onClick = { styleMenu = true }, modifier = Modifier.fillMaxWidth()) {
                    Text("阅读风格：${Styles.keys[state.settings.readingStyle] ?: "米黄纸"}", fontSize = 14.sp)
                }
                DropdownMenu(expanded = styleMenu, onDismissRequest = { styleMenu = false }) {
                    Styles.keys.forEach { (k, label) ->
                        DropdownMenuItem(text = { Text(label) }, onClick = {
                            state.settings = state.settings.copy(readingStyle = k)
                            styleMenu = false
                        })
                    }
                }
            }

            // 字号
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("正文字号", color = pal.text, fontSize = 14.sp, modifier = Modifier.width(80.dp))
                Slider(
                    value = state.settings.fontSize.toFloat(),
                    onValueChange = { state.settings = state.settings.copy(fontSize = it.toInt()) },
                    valueRange = 12f..32f,
                    modifier = Modifier.weight(1f),
                )
                Text("${state.settings.fontSize}", color = pal.text, fontSize = 13.sp)
            }

            // 自动执行
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("自动执行文件操作", color = pal.text, fontSize = 14.sp, modifier = Modifier.weight(1f))
                Switch(
                    checked = state.settings.autoExec,
                    onCheckedChange = { state.settings = state.settings.copy(autoExec = it) },
                )
            }

            // 保存
            Button(
                onClick = { state.saveSettings(); status = "[OK] 已保存" },
                colors = ButtonDefaults.buttonColors(containerColor = pal.accent),
                modifier = Modifier.fillMaxWidth(),
            ) { Text("保存设置", fontSize = 16.sp) }
        }
    }
}
