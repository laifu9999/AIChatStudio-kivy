package com.aichatstudio.app.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowUpward
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.KeyboardArrowUp
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.nestedscroll.NestedScrollConnection
import androidx.compose.ui.input.nestedscroll.NestedScrollSource
import androidx.compose.ui.input.nestedscroll.nestedScroll
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.aichatstudio.app.data.ChatMessage
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlin.math.abs

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
    val focusManager = LocalFocusManager.current
    val msgs = state.messages

    // 渲染列表 = 真实消息 + （流式时）一条临时打字气泡，让打字效果在聊天窗口全屏显示完整内容
    val displayList = if (state.streamingActive) {
        msgs + ChatMessage("assistant", state.streamingText)
    } else msgs

    // 新消息（含流式开始）出现时，平滑滚到底
    LaunchedEffect(displayList.size) {
        if (displayList.isNotEmpty()) {
            listState.animateScrollToItem(displayList.lastIndex)
        }
    }
    // 流式结束后，把最终回复平滑滚到底（默认最底部，不跳回顶部）
    LaunchedEffect(state.streamingActive) {
        if (!state.streamingActive && displayList.isNotEmpty()) {
            listState.animateScrollToItem(displayList.lastIndex)
        }
    }
    // 流式打字中：仅当用户已在底部附近时即时跟随最底，保证最新字符可见且不抢走阅读
    LaunchedEffect(state.streamingText) {
        if (state.streamingActive) {
            val info = listState.layoutInfo
            val lastIdx = info.totalItemsCount - 1
            val lastVisible = info.visibleItemsInfo.lastOrNull()?.index ?: 0
            if (lastVisible >= lastIdx - 1) {
                listState.scrollToItem(lastIdx)
            }
        }
    }

    // 快速滑动时显示回顶/回底小箭头
    val showArrows = remember { mutableStateOf(false) }
    val lastScrollTime = remember { mutableStateOf(0L) }
    LaunchedEffect(lastScrollTime.value) {
        delay(1200)
        if (System.currentTimeMillis() - lastScrollTime.value >= 1000) {
            showArrows.value = false
        }
    }
    val nestedScrollConnection = remember {
        object : NestedScrollConnection {
            override fun onPostScroll(
                consumed: Offset,
                available: Offset,
                source: NestedScrollSource,
            ): Offset {
                if (abs(consumed.y) > 30f) {
                    showArrows.value = true
                    lastScrollTime.value = System.currentTimeMillis()
                }
                return Offset.Zero
            }
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(pal.bg)
            .imePadding()
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
        Box(
            modifier = Modifier
                .weight(1f)
                .nestedScroll(nestedScrollConnection)
        ) {
            LazyColumn(
                state = listState,
                modifier = Modifier.fillMaxSize(),
                contentPadding = PaddingValues(horizontal = 10.dp, vertical = 6.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                items(displayList) { m ->
                    MessageBubble(
                        m,
                        pal,
                        Styles.fontFamilyOf(state.settings.fontFamily),
                        state.settings.showThinking,
                    )
                }
            }

            // 回顶/回底小箭头：默认隐藏，快速滑动时出现
            if (showArrows.value) {
                Column(
                    modifier = Modifier
                        .align(Alignment.BottomEnd)
                        .padding(8.dp),
                    verticalArrangement = Arrangement.spacedBy(6.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) {
                    SmallScrollButton(
                        icon = Icons.Default.KeyboardArrowUp,
                        contentDescription = "回顶",
                        onClick = { scope.launch { listState.scrollToItem(0) } },
                        pal = pal,
                    )
                    SmallScrollButton(
                        icon = Icons.Default.KeyboardArrowDown,
                        contentDescription = "回底",
                        onClick = { scope.launch { if (displayList.isNotEmpty()) listState.scrollToItem(displayList.lastIndex) } },
                        pal = pal,
                    )
                }
            }
        }

        // 输入栏：圆角输入框 + 右侧圆形发送/停止按钮
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .background(pal.panel)
                .padding(horizontal = 8.dp, vertical = 6.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            OutlinedTextField(
                value = state.inputText,
                onValueChange = { state.inputText = it },
                placeholder = { Text("输入消息…", fontSize = 14.sp) },
                modifier = Modifier.weight(1f),
                textStyle = LocalTextStyle.current.copy(fontSize = 15.sp, color = pal.text),
                shape = RoundedCornerShape(24.dp),
                maxLines = 4,
                trailingIcon = {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        TextButton(onClick = {
                            val t = state.pasteText()
                            if (t.isNotEmpty()) state.inputText = state.inputText + t
                        }) { Text("粘贴", color = pal.text, fontSize = 12.sp) }
                        Spacer(Modifier.width(2.dp))
                        SendStopButton(
                            streaming = state.streaming,
                            enabled = !state.streaming && state.inputText.trim().isNotEmpty(),
                            onClick = {
                                if (state.streaming) {
                                    state.stop()
                                } else {
                                    val t = state.inputText.trim()
                                    if (t.isNotEmpty()) {
                                        focusManager.clearFocus()
                                        state.send(t)
                                        scope.launch {
                                            if (displayList.isNotEmpty()) {
                                                listState.animateScrollToItem(displayList.lastIndex)
                                            }
                                        }
                                    }
                                }
                            },
                        )
                    }
                },
            )
        }
    }
}

@Composable
fun MessageBubble(
    m: ChatMessage,
    pal: Styles.Palette,
    fontFamily: FontFamily = FontFamily.Default,
    showThinking: Boolean = false,
) {
    val isUser = m.role == "user"
    val bubbleColor = if (isUser) pal.userBubble else pal.aiBubble
    val (reason, answer) = remember(m.content) { extractThink(m.content) }
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = if (isUser) Arrangement.End else Arrangement.Center,
    ) {
        SelectionContainer {
            Column(
                modifier = Modifier.fillMaxWidth(if (isUser) 0.86f else 1f),
            ) {
            if (!isUser && showThinking && reason.isNotEmpty()) {
                Text(
                    text = reason,
                    color = pal.textDim,
                    fontSize = 13.sp,
                    lineHeight = 18.sp,
                    fontFamily = fontFamily,
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(12.dp))
                        .background(pal.panel)
                        .padding(horizontal = 12.dp, vertical = 6.dp),
                )
                Spacer(Modifier.height(4.dp))
            }
            Text(
                text = if (isUser) m.content else answer,
                color = pal.text,
                fontSize = 16.sp,
                lineHeight = 22.sp,
                fontFamily = fontFamily,
                textAlign = if (isUser) TextAlign.Start else TextAlign.Center,
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(12.dp))
                    .background(bubbleColor)
                    .padding(horizontal = 12.dp, vertical = 8.dp),
            )
            }
        }
    }
}

@Composable
private fun SmallScrollButton(
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    contentDescription: String,
    onClick: () -> Unit,
    pal: Styles.Palette,
) {
    Surface(
        shape = CircleShape,
        color = pal.accent.copy(alpha = 0.9f),
        modifier = Modifier.size(34.dp),
        shadowElevation = 2.dp,
    ) {
        IconButton(onClick = onClick) {
            Icon(
                imageVector = icon,
                contentDescription = contentDescription,
                tint = Color.White,
                modifier = Modifier.size(20.dp),
            )
        }
    }
}

@Composable
private fun SendStopButton(
    streaming: Boolean,
    enabled: Boolean,
    onClick: () -> Unit,
) {
    val clickable = streaming || enabled
    val container = when {
        streaming -> Color(0xFF5C4033)
        enabled -> Color.Black
        else -> Color.LightGray
    }
    Surface(
        shape = CircleShape,
        color = container,
        modifier = Modifier
            .padding(4.dp)
            .size(42.dp),
    ) {
        Box(contentAlignment = Alignment.Center) {
            IconButton(
                onClick = onClick,
                enabled = clickable,
                modifier = Modifier.fillMaxSize(),
            ) {
                if (streaming) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(22.dp),
                        color = Color.White,
                        strokeWidth = 2.dp,
                    )
                } else {
                    Icon(
                        imageVector = Icons.Default.ArrowUpward,
                        contentDescription = "发送",
                        tint = Color.White,
                        modifier = Modifier.size(22.dp),
                    )
                }
            }
        }
    }
}

private fun extractThink(content: String): Pair<String, String> {
    val regex = Regex("```thinking\\s*\\n(.*?)```", RegexOption.DOT_MATCHES_ALL)
    val m = regex.find(content)
    return if (m != null) {
        m.groupValues[1].trim() to content.removeRange(m.range).trim()
    } else {
        "" to content
    }
}
