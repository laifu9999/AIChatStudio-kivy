package com.aichatstudio.app.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.launch
import java.io.File
import java.nio.charset.Charset

/** 阅读窗口：项目文件浏览 / 打开 / 编辑保存 / 阅读风格 / 字号 / 回顶回底。 */
@Composable
fun ReaderScreen(state: AppState, onBack: () -> Unit) {
    val pal = Styles.palette(state.settings.readingStyle)
    var fileList by remember { mutableStateOf<List<Pair<String, File>>?>(null) }
    var currentFile by remember { mutableStateOf<File?>(null) }
    var content by remember { mutableStateOf("") }
    var editing by remember { mutableStateOf(false) }
    var editText by remember { mutableStateOf("") }
    var title by remember { mutableStateOf("阅读窗口") }
    var fs by remember { mutableStateOf(state.settings.fontSize) }
    val fontFamily = Styles.fontFamilyOf(state.settings.fontFamily)
    var status by remember { mutableStateOf("") }
    val scroll = rememberScrollState()
    val scope = rememberCoroutineScope()

    fun loadFile(f: File) {
        currentFile = f
        content = try { f.readText(Charsets.UTF_8) } catch (e: Exception) {
            try { f.readText(Charset.forName("GBK")) } catch (e2: Exception) { "[!] 打开失败：${e2.message}" }
        }
        editing = false
        title = f.name
        status = ""
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
            TextButton(onClick = onBack) { Text("← 聊天", color = pal.text, fontSize = 14.sp) }
            Text(title, color = pal.text, fontSize = 14.sp, modifier = Modifier.weight(1f),
                maxLines = 1)
            TextButton(onClick = { if (fs > 10) fs -= 2 }) { Text("A-", color = pal.text) }
            TextButton(onClick = { if (fs < 48) fs += 2 }) { Text("A+", color = pal.text) }
            TextButton(onClick = {
                if (currentFile != null) {
                    if (!editing) {
                        editing = true; editText = content
                    } else {
                        try {
                            currentFile!!.writeText(editText, Charsets.UTF_8)
                            content = editText; editing = false
                            status = "已保存：${currentFile!!.name}"
                        } catch (e: Exception) { status = "保存失败：${e.message}" }
                    }
                } else status = "请先打开文件"
            }) { Text(if (editing) "保存" else "修改", color = pal.accent, fontSize = 14.sp) }
        }

        // 路径操作条
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .background(pal.panel)
                .padding(horizontal = 6.dp, vertical = 4.dp),
            horizontalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            TextButton(onClick = {
                val files = state.listProjectFiles()
                fileList = files
                if (files.isEmpty()) status = "（会话还没有文件，让 AI 用 %%FILE: 生成）"
            }) { Text("项目文件", color = pal.text, fontSize = 13.sp) }
            TextButton(onClick = {
                fileList = state.listDir(state.store.root).map { it.first to it.second }
            }) { Text("应用目录", color = pal.text, fontSize = 13.sp) }
            TextButton(onClick = { scope.launch { scroll.scrollTo(0) } }) { Text("回顶", color = pal.text, fontSize = 13.sp) }
            TextButton(onClick = { scope.launch { scroll.scrollTo(scroll.maxValue) } }) { Text("回底", color = pal.text, fontSize = 13.sp) }
        }

        // 文件列表（点击打开 / 目录则进入）
        fileList?.let { files ->
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(pal.panel)
                    .padding(vertical = 2.dp)
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text("文件 ${files.size} 个（点开查看/阅读/修改）", color = pal.textDim,
                        fontSize = 12.sp, modifier = Modifier.weight(1f).padding(start = 10.dp))
                    TextButton(onClick = { fileList = null }) { Text("收起", fontSize = 12.sp) }
                }
                files.take(80).forEach { (rel, f) ->
                    TextButton(
                        onClick = {
                            if (f.isDirectory) {
                                fileList = state.listDir(f).map { rel + "/" + it.first to it.second }
                            } else loadFile(f)
                        },
                        modifier = Modifier.fillMaxWidth(),
                    ) { Text((if (f.isDirectory) "📁 " else "") + rel, color = pal.text,
                        fontSize = 13.sp, maxLines = 1) }
                }
            }
        }

        // 正文 / 编辑
        if (editing) {
            OutlinedTextField(
                value = editText,
                onValueChange = { editText = it },
                modifier = Modifier
                    .fillMaxWidth()
                    .weight(1f),
                textStyle = TextStyle(fontSize = fs.sp, color = pal.text),
            )
        } else {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .weight(1f)
                    .verticalScroll(scroll)
                    .padding(horizontal = 16.dp, vertical = 12.dp)
            ) {
                Text(content, color = pal.text, fontSize = fs.sp, lineHeight = (fs + 6).sp, fontFamily = fontFamily)
            }
        }

        if (status.isNotEmpty()) {
            Text(status, color = pal.textDim, fontSize = 12.sp,
                modifier = Modifier.padding(horizontal = 12.dp, vertical = 4.dp))
        }
    }
}
