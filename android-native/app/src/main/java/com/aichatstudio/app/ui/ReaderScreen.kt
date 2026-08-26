package com.aichatstudio.app.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
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
    val editFocus = remember { FocusRequester() }
    var dirStack by remember { mutableStateOf<List<File>>(emptyList()) }

    // 进入编辑时自动聚焦并弹出输入法；配合 imePadding 整体上移，输入框不被键盘盖住
    LaunchedEffect(editing) {
        if (editing) {
            kotlinx.coroutines.delay(120)
            editFocus.requestFocus()
        }
    }

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
                val folder = state.current?.folder
                if (folder != null) {
                    dirStack = listOf(folder)
                    fileList = state.listDir(folder)
                    if (fileList.isNullOrEmpty()) status = "（会话还没有文件，让 AI 用 %%FILE: 生成）"
                }
            }) { Text("项目文件", color = pal.text, fontSize = 13.sp) }
            TextButton(onClick = {
                dirStack = listOf(state.store.root)
                fileList = state.listDir(state.store.root)
            }) { Text("应用目录", color = pal.text, fontSize = 13.sp) }
            TextButton(onClick = { scope.launch { scroll.scrollTo(0) } }) { Text("回顶", color = pal.text, fontSize = 13.sp) }
            TextButton(onClick = { scope.launch { scroll.scrollTo(scroll.maxValue) } }) { Text("回底", color = pal.text, fontSize = 13.sp) }
        }

        // 文件列表（点击打开 / 目录则进入；支持返回上一级、在手机文件管理器打开所在位置）
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
                    TextButton(onClick = {
                        if (dirStack.size > 1) {
                            dirStack = dirStack.dropLast(1)
                            fileList = state.listDir(dirStack.last())
                            status = "已返回上一级：${dirStack.last().path}"
                        } else status = "已在最上级目录"
                    }) { Text("上一级", color = pal.text, fontSize = 12.sp) }
                    TextButton(onClick = {
                        val d = dirStack.lastOrNull() ?: state.store.root
                        val ok = state.openFolderOnPhone(d)
                        // 无论如何都把应用内文件浏览器定位到该目录，保证一定能看到位置
                        val root = state.store.root
                        dirStack = if (d.path.startsWith(root.path)) {
                            val st = mutableListOf<File>()
                            var cur: File? = d
                            while (cur != null && cur.path != root.path) { st.add(0, cur); cur = cur.parentFile }
                            st.add(0, root); st
                        } else mutableListOf(d)
                        fileList = state.listDir(d)
                        status = if (ok) "已尝试在系统文件管理器打开：${d.path}\n（路径已复制，可在文件管理器粘贴定位）"
                                 else "已为你定位到应用内文件列表：${d.path}\n（本机文件管理器无法打开该位置，路径已复制）"
                    }) { Text("打开位置", color = pal.text, fontSize = 12.sp) }
                    TextButton(onClick = { fileList = null }) { Text("收起", fontSize = 12.sp) }
                }
                files.take(80).forEach { (name, f) ->
                    TextButton(
                        onClick = {
                            if (f.isDirectory) {
                                dirStack = dirStack + f
                                fileList = state.listDir(f)
                                status = f.path
                            } else loadFile(f)
                        },
                        modifier = Modifier.fillMaxWidth(),
                    ) { Text((if (f.isDirectory) "📁 " else "") + name, color = pal.text,
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
                    .weight(1f)
                    .focusRequester(editFocus),
                textStyle = TextStyle(fontSize = fs.sp, color = pal.text),
            )
        } else {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .weight(1f)
                    .verticalScroll(scroll)
                    .padding(horizontal = 16.dp, vertical = 12.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                Text(
                    content,
                    color = pal.text,
                    fontSize = fs.sp,
                    lineHeight = (fs + 6).sp,
                    fontFamily = fontFamily,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        }

        if (status.isNotEmpty()) {
            Text(status, color = pal.textDim, fontSize = 12.sp,
                modifier = Modifier.padding(horizontal = 12.dp, vertical = 4.dp))
        }
    }
}
