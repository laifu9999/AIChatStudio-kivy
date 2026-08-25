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
import java.io.File

/** 投喂设置：每个会话一次文字投喂 + 指定文件无限次投喂 + 自动续章开关/章数。 */
@Composable
fun FeedScreen(state: AppState, onBack: () -> Unit) {
    val pal = Styles.palette(state.settings.readingStyle)
    var status by remember { mutableStateOf("") }
    var pickFiles by remember { mutableStateOf<List<Pair<String, File>>?>(null) }

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
            Text("投喂与续章", color = pal.text, fontSize = 17.sp, fontWeight = FontWeight.Bold)
        }

        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(14.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            // 总开关
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("启用投喂", color = pal.text, fontSize = 15.sp, modifier = Modifier.weight(1f))
                Switch(
                    checked = state.feed.enabled,
                    onCheckedChange = { state.feed = state.feed.copy(enabled = it); state.saveFeed() },
                )
            }

            HorizontalDivider()

            // 每个会话一次投喂
            Text("每个会话一次投喂（切换会话后自动再次触发）", color = pal.textDim, fontSize = 13.sp)
            OutlinedTextField(
                value = state.feed.firstText,
                onValueChange = { state.feed = state.feed.copy(firstText = it); state.saveFeed() },
                label = { Text("首次投喂内容") },
                modifier = Modifier.fillMaxWidth(),
                minLines = 3,
            )

            HorizontalDivider()

            // 指定文件（无限次投喂）
            Text("指定文件注入投喂（无限次，每次发送都会带上）", color = pal.textDim, fontSize = 13.sp)
            state.feed.feedFiles.forEach { path ->
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(path, color = pal.text, fontSize = 13.sp, modifier = Modifier.weight(1f),
                        maxLines = 1)
                    TextButton(onClick = {
                        state.feed = state.feed.copy(
                            feedFiles = state.feed.feedFiles.filter { it != path }.toMutableList()
                        )
                        state.saveFeed()
                    }) { Text("删除", color = MaterialTheme.colorScheme.error, fontSize = 13.sp) }
                }
            }
            // 从应用目录选择文件加入
            Button(onClick = {
                val files = state.listProjectFiles()
                if (files.isEmpty()) { status = "当前会话还没有文件" }
                else {
                    pickFiles = files
                    status = "共 ${files.size} 个文件，点击「添加」加入投喂："
                }
            }) { Text("选择文件", fontSize = 14.sp) }

            // 待选文件列表（点击添加）
            pickFiles?.forEach { (rel, file) ->
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(rel, color = pal.text, fontSize = 13.sp, modifier = Modifier.weight(1f),
                        maxLines = 1)
                    TextButton(onClick = {
                        if (!state.feed.feedFiles.contains(file.absolutePath)) {
                            state.feed = state.feed.copy(
                                feedFiles = (state.feed.feedFiles + file.absolutePath).toMutableList()
                            )
                            state.saveFeed()
                        }
                        status = "已添加：$rel"
                    }) { Text("添加", color = pal.accent, fontSize = 13.sp) }
                }
            }
            if (pickFiles != null) {
                TextButton(onClick = { pickFiles = null }) { Text("收起列表", fontSize = 12.sp) }
            }

            HorizontalDivider()

            // 自动续章
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("自动续章", color = pal.text, fontSize = 15.sp, modifier = Modifier.weight(1f))
                Switch(
                    checked = state.feed.autoContinue,
                    onCheckedChange = { state.feed = state.feed.copy(autoContinue = it); state.saveFeed() },
                )
            }
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("续章数(1~300)", color = pal.text, fontSize = 14.sp, modifier = Modifier.width(100.dp))
                OutlinedTextField(
                    value = state.feed.maxRounds.toString(),
                    onValueChange = {
                        val n = it.filter { c -> c.isDigit() }.toIntOrNull() ?: 1
                        state.feed = state.feed.copy(maxRounds = n.coerceIn(1, 300)); state.saveFeed()
                    },
                    singleLine = true,
                    modifier = Modifier.width(100.dp),
                )
                Text(" 章", color = pal.text, fontSize = 13.sp)
            }
            Text("续章时随机等待 3~6 秒，并自动注入投喂内容", color = pal.textDim, fontSize = 12.sp)

            if (status.isNotEmpty()) {
                Text(status, color = pal.textDim, fontSize = 13.sp)
            }
        }
    }
}
