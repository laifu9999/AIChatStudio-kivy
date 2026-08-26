package com.aichatstudio.app

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Environment
import android.provider.Settings
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
                val needed = mutableListOf<String>().apply {
                    add(Manifest.permission.READ_EXTERNAL_STORAGE)
                    if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) {
                        add(Manifest.permission.WRITE_EXTERNAL_STORAGE)
                    }
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                        add(Manifest.permission.READ_MEDIA_IMAGES)
                        add(Manifest.permission.READ_MEDIA_VIDEO)
                        add(Manifest.permission.READ_MEDIA_AUDIO)
                    }
                }
                val missing = needed.filter {
                    ContextCompat.checkSelfPermission(this@MainActivity, it) != PackageManager.PERMISSION_GRANTED
                }
                if (missing.isNotEmpty()) permLauncher.launch(missing.toTypedArray())

                // Android 11+「所有文件访问」：必须跳转到系统设置授权
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R &&
                    !Environment.isExternalStorageManager()
                ) {
                    try {
                        val intent = Intent(Settings.ACTION_MANAGE_ALL_FILES_ACCESS_PERMISSION)
                        intent.data = Uri.parse("package:$packageName")
                        startActivity(intent)
                    } catch (_: Exception) {
                        val intent = Intent(Settings.ACTION_MANAGE_ALL_FILES_ACCESS_PERMISSION)
                        startActivity(intent)
                    }
                }
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

/** 会话抽屉：新建 / 切换 / 批量删除（带确认弹窗）。 */
@Composable
private fun SessionsDrawer(
    state: AppState,
    onDismiss: () -> Unit,
    onSelect: (String) -> Unit,
) {
    val pal = Styles.palette(state.settings.readingStyle)
    var selectMode by remember { mutableStateOf(false) }
    var selected by remember { mutableStateOf<Set<String>>(emptySet()) }
    var confirmDelete by remember { mutableStateOf(false) }

    // 全屏模态：半透明遮罩 + 中央面板
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
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        "会话",
                        color = pal.text,
                        fontSize = 17.sp,
                        fontWeight = FontWeight.Bold,
                        modifier = Modifier.weight(1f),
                    )
                    if (selectMode) {
                        TextButton(onClick = {
                            selected = if (selected.size == state.sessions.size && state.sessions.isNotEmpty())
                                emptySet()
                            else state.sessions.map { it.id }.toSet()
                        }) { Text("全选", color = pal.text, fontSize = 13.sp) }
                        TextButton(
                            onClick = { confirmDelete = true },
                            enabled = selected.isNotEmpty(),
                        ) { Text("删除(${selected.size})", color = MaterialTheme.colorScheme.error, fontSize = 13.sp) }
                        TextButton(onClick = {
                            selectMode = false
                            selected = emptySet()
                        }) { Text("取消", color = pal.text, fontSize = 13.sp) }
                    } else {
                        TextButton(onClick = { selectMode = true }) {
                            Text("批量删除", color = pal.text, fontSize = 13.sp)
                        }
                    }
                }
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
                        val checked = s.id in selected
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            if (selectMode) {
                                Checkbox(checked = checked, onCheckedChange = {
                                    selected = if (checked) selected - s.id else selected + s.id
                                })
                            }
                            TextButton(
                                onClick = {
                                    if (selectMode) {
                                        selected = if (checked) selected - s.id else selected + s.id
                                    } else onSelect(s.id)
                                },
                                modifier = Modifier.weight(1f),
                            ) {
                                Text(s.name, color = pal.text, fontSize = 14.sp, maxLines = 1)
                            }
                            if (!selectMode) {
                                TextButton(onClick = { state.deleteSession(s.id) }) {
                                    Text("删", color = MaterialTheme.colorScheme.error, fontSize = 13.sp)
                                }
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

    // 删除确认弹窗
    if (confirmDelete) {
        AlertDialog(
            onDismissRequest = { confirmDelete = false },
            title = { Text("确认删除") },
            text = { Text("确定要删除这 ${selected.size} 个会话吗？\n此操作不可撤销。") },
            confirmButton = {
                TextButton(onClick = {
                    val ids = selected.toList()
                    for (id in ids) state.deleteSession(id)
                    selected = emptySet()
                    selectMode = false
                    confirmDelete = false
                }) { Text("确认删除", color = MaterialTheme.colorScheme.error) }
            },
            dismissButton = {
                TextButton(onClick = { confirmDelete = false }) { Text("取消") }
            },
        )
    }
}
