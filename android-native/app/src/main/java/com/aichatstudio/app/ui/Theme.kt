package com.aichatstudio.app.ui

import androidx.compose.ui.graphics.Color

/** 阅读小说风格配色（与桌面版一致）。 */
object Styles {
    data class Palette(
        val bg: Color,
        val panel: Color,
        val text: Color,
        val textDim: Color,
        val accent: Color,
        val userBubble: Color,
        val aiBubble: Color,
    )

    val cream = Palette(
        bg = Color(0xFFFBF6E9), panel = Color(0xFFF3ECDA),
        text = Color(0xFF3E3220), textDim = Color(0xFF8A7A5E),
        accent = Color(0xFFB8860B), userBubble = Color(0xFFE6D8B8), aiBubble = Color(0xFFF4EEDC),
    )
    val green = Palette(
        bg = Color(0xFFDDEBD8), panel = Color(0xFFCFE0C8),
        text = Color(0xFF27462A), textDim = Color(0xFF6B8A6E),
        accent = Color(0xFF3E8E4E), userBubble = Color(0xFFBED7B8), aiBubble = Color(0xFFE4F0E0),
    )
    val night = Palette(
        bg = Color(0xFF1E2430), panel = Color(0xFF2A3140),
        text = Color(0xFFD8DCE4), textDim = Color(0xFF8A93A6),
        accent = Color(0xFF5B8DEF), userBubble = Color(0xFF37415A), aiBubble = Color(0xFF262E3D),
    )
    val parchment = Palette(
        bg = Color(0xFFF5EED9), panel = Color(0xFFEDE2C6),
        text = Color(0xFF5A4A2A), textDim = Color(0xFFA08A5E),
        accent = Color(0xFF8C6D1F), userBubble = Color(0xFFE2D3AE), aiBubble = Color(0xFFF7F0DE),
    )
    val white = Palette(
        bg = Color(0xFFFFFFFF), panel = Color(0xFFF2F2F2),
        text = Color(0xFF222222), textDim = Color(0xFF999999),
        accent = Color(0xFF2979FF), userBubble = Color(0xFFE3F2FD), aiBubble = Color(0xFFF5F5F5),
    )

    val keys = mapOf(
        "cream" to "米黄纸", "green" to "护眼绿", "night" to "夜间",
        "parchment" to "羊皮卷", "white" to "简约白",
    )

    fun palette(key: String): Palette = when (key) {
        "green" -> green; "night" -> night; "parchment" -> parchment; "white" -> white
        else -> cream
    }
}
