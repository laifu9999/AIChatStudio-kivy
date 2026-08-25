package com.aichatstudio.app.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.aichatstudio.app.data.ChatMessage
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChatScreen(
    state: AppState,
    onOpenSessions: () -> Unit,
    onOpenSettings: () -> Unit,
    onOpenFeed: () -> Unit,
    onOpenReader: () -> Unit,
) {
    val pal = Styles.palette(state.settings.readingStyle)
    val listState = rememberLazyListState()
    val scope = rememberCoroutineScope()
    val msgs = state.messages

    // 新消息自动滚到底
    LaunchedEffect(msgs.size) {
        if (msgs.isNotEmpty()) {
            listState.animateScrollToItem(msgs.size - 1)
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(pal.bg)
    ) {
        // 顶栏
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .background(pal.panel)
                .padding(horizontal = 4.dp, vertical = 6.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            TextButton(onClick = onOpenSessions) { Text("会话", color = pal.text, fontSize = 14.sp) }
            Text(
                text = state.settings.provider.ifEmpty { "未配置AI" },
                color = pal.textDim, fontSize = 12.sp,
                modifier = Modifier.weight(1f),
                maxLines = 1,
            )
            TextButton(onClick = onOpenReader) { Text("阅读", color = pal.text, fontSize = 14.sp) }
            TextButton(onClick = onOpenFeed) { Text("投喂", color = pal.text, fontSize = 14.sp) }
            TextButton(onClick = onOpenSettings) { Text("设置", color = pal.text, fontSize = 14.sp) }
        }

        // 投喂/续章状态条
        if (state.feedStatus.isNotEmpty()) {
            Text(
                text = state.feedStatus,
                color = pal.accent, fontSize = 11.sp,
                modifier = Modifier
                    .fillMaxWidth()
                    .background(pal.panel)
                    .padding(horizontal = 8.dp, vertical = 3.dp),
                maxLines = 1,
            )
        }

        // 消息列表
        Box(modifier = Modifier.weight(1f)) {
            LazyColumn(
                state = listState,
                modifier = Modifier.fillMaxSize(),
                contentPadding = PaddingValues(horizontal = 10.dp, vertical = 6.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                items(msgs) { m ->
                    MessageBubble(m, pal)
                }
            }
            // 回顶/回底
            Column(
                modifier = Modifier
                    .align(Alignment.BottomEnd)
                    .padding(8.dp),
                verticalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                FilledTonalButton(onClick = { scope.launch { listState.scrollToItem(0) } },
                    modifier = Modifier.size(width = 64.dp, height = 34.dp)) {
                    Text("顶部", fontSize = 11.sp)
                }
                FilledTonalButton(onClick = { scope.launch { listState.scrollToItem(msgs.size - 1) } },
                    modifier = Modifier.size(width = 64.dp, height = 34.dp)) {
                    Text("底部", fontSize = 11.sp)
                }
            }
        }

        // 输入栏
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .background(pal.panel)
                .padding(6.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            OutlinedTextField(
                value = state.inputText,
                onValueChange = { state.inputText = it },
                placeholder = { Text("输入消息…", fontSize = 14.sp) },
                modifier = Modifier.weight(1f),
                textStyle = LocalTextStyle.current.copy(fontSize = 15.sp, color = pal.text),
            )
            Spacer(Modifier.width(4.dp))
            TextButton(onClick = {
                val t = state.pasteText()
                if (t.isNotEmpty()) state.inputText = state.inputText + t
            }) { Text("粘贴", color = pal.text, fontSize = 13.sp) }
            Column {
                Button(
                    onClick = { state.send(state.inputText) },
                    enabled = !state.streaming,
                    colors = ButtonDefaults.buttonColors(containerColor = pal.accent),
                    modifier = Modifier.fillMaxWidth(),
                ) { Text("发送", fontSize = 14.sp) }
                OutlinedButton(
                    onClick = { state.stop() },
                    enabled = state.streaming,
                    modifier = Modifier.fillMaxWidth(),
                ) { Text("停止", fontSize = 12.sp) }
            }
        }
    }
}

@Composable
fun MessageBubble(m: ChatMessage, pal: Styles.Palette) {
    val isUser = m.role == "user"
    val bubbleColor = if (isUser) pal.userBubble else pal.aiBubble
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = if (isUser) Arrangement.End else Arrangement.Start,
    ) {
        Text(
            text = m.content,
            color = pal.text,
            fontSize = 16.sp,
            lineHeight = 22.sp,
            modifier = Modifier
                .fillMaxWidth(0.86f)
                .clip(RoundedCornerShape(12.dp))
                .background(bubbleColor)
                .padding(horizontal = 12.dp, vertical = 8.dp),
        )
    }
}
