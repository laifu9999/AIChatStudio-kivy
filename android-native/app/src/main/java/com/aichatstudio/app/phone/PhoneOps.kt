package com.aichatstudio.app.phone

import android.content.Context
import android.content.Intent
import android.net.Uri

object PhoneOps {
    fun parseOpenUrls(context: Context, text: String): List<String> {
        val regex = Regex("```open_url\\s+(.*?)```", RegexOption.DOT_MATCHES_ALL)
        return regex.findAll(text).mapNotNull { m ->
            val url = m.groupValues[1].trim()
            if (url.isEmpty()) null else if (openUrl(context, url)) url else null
        }.toList()
    }

    fun openUrl(context: Context, url: String): Boolean {
        val u = url.trim()
        if (u.isEmpty()) return false
        val full = if (u.startsWith("http://") || u.startsWith("https://")) u else "https://$u"
        return try {
            val intent = Intent(Intent.ACTION_VIEW, Uri.parse(full))
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            context.startActivity(intent)
            true
        } catch (e: Exception) {
            false
        }
    }
}
