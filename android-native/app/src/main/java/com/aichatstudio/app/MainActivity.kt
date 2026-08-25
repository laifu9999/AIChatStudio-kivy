package com.aichatstudio.app

import android.Manifest
import android.content.pm.PackageManager
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import androidx.lifecycle.viewmodel.compose.viewModel
import com.aichatstudio.app.ui.*
import java.io.File

enum class Screen { Chat, Settings, Feed, Reader }

class MainActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            val state: AppState = viewModel()
            var screen by remember { mutableStateOf(Screen.Chat) }
            var showSessions by remember { mutableStateOf(false) }

            // Android 6+ 运行时权限（应用专属目录无需权限；请求存储权限供浏览外部路径）
            val permLauncher = rememberLauncherForActivityResult(
                ActivityResultContracts.RequestMultiplePermissions()
            ) {}
            LaunchedEffect(Unit) {
                val needed = listOf(
                    Manifest.permission.READ_EXTERNAL_STORAGE,
                    Manifest.permission.WRITE_EXTERNAL_STORAGE,
                )
                val missing = needed.filter {
                    ContextCompat.checkSelfPermission(this@MainActivity, it) != PackageManager.PERMISSION_GRANTED
                }
                if (missing.isNotEmpty()) permLauncher.launch(missing.toTypedArray())
            }

            MaterialTheme(colorScheme = lightColorScheme()) {
                when (screen) {
                    Screen.Chat -> ChatScreen(
                        state = state,
                        onOpenSessions = { showSessions = true },
                        onOpenSettings = { screen = Screen.Settings },
                        onOpenFeed = { screen = Screen.Feed },
                        onOpenReader = { screen = Screen.Reader },
                    )
                    Screen.Settings -> SettingsScreen(state) { screen = Screen.Chat }
                    Screen.Feed -> FeedScreen(state) { screen = Screen.Chat }
                    Screen.Reader -> ReaderScreen(state) { screen = Screen.Chat }
                }

                // 会话抽屉
                if (showSessions) {
                    SessionsDrawer(
                        state = state,
                        onDismiss = { showSessions = false },
                        onSelect = {
                            state.selectSession(it)
                            showSessions = false
                            screen = Screen.Chat
                        },
                    )
                }
            }
        }
    }
}

/** 会话抽屉：新建 / 切换 / 删除。 */
@Composable
private fun SessionsDrawer(
    state: AppState,
    onDismiss: () -> Unit,
    onSelect: (String) -> Unit,
) {
    val pal = Styles.palette(state.settings.readingStyle)
    var pick by remember { mutableStateOf(false) }

    // 简单的全屏模态：半透明遮罩 + 中央面板
    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(androidx.compose.ui.graphics.Color(0x66000000)),
    ) {
        Surface(
            modifier = Modifier
                .align(Alignment.Center)
                .fillMaxWidth(0.88f)
                .fillMaxHeight(0.82f),
            color = pal.bg,
            shadowElevation = 12.dp,
            shape = MaterialTheme.shapes.medium,
        ) {
            Column(modifier = Modifier.padding(12.dp)) {
                Text("会话", color = pal.text, fontSize = 17.sp, fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(8.dp))
                Button(
                    onClick = {
                        state.newSession()
                        onSelect(state.current?.meta?.id ?: "")
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = pal.accent),
                    modifier = Modifier.fillMaxWidth(),
                ) { Text("+ 新建会话", fontSize = 14.sp) }
                Spacer(Modifier.height(8.dp))
                androidx.compose.foundation.lazy.LazyColumn(
                    modifier = Modifier.weight(1f),
                    verticalArrangement = Arrangement.spacedBy(4.dp),
                ) {
                    items(state.sessions.size) { i ->
                        val s = state.sessions[i]
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            TextButton(onClick = { onSelect(s.id) },
                                modifier = Modifier.weight(1f)) {
                                Text(s.name, color = pal.text, fontSize = 14.sp, maxLines = 1)
                            }
                            TextButton(onClick = { state.deleteSession(s.id) }) {
                                Text("删", color = MaterialTheme.colorScheme.error, fontSize = 13.sp)
                            }
                        }
                    }
                }
                Spacer(Modifier.height(8.dp))
                TextButton(onClick = onDismiss, modifier = Modifier.fillMaxWidth()) {
                    Text("关闭", color = pal.text, fontSize = 15.sp)
                }
            }
        }
    }
}
