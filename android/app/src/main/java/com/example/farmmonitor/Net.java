package com.example.farmmonitor;

import android.content.Context;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;

import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

/**
 * Сетевые вызовы. Сообщает ТОЛЬКО настоящие данные устройства:
 * публичный IP, провайдера, страну, тип подключения.
 *
 * Здесь нет и не будет прокси, VPN, подмены IP или геолокации.
 */
public final class Net {

    static final String IP_URL = "https://api.ipify.org?format=json";
    static final String META_URL = "https://ipapi.co/%s/json/";
    private static final int TIMEOUT_MS = 12000;

    private Net() {}

    public static class Info {
        public String ip;
        public String org;
        public String country;
        public String connType;
        public String error;
    }

    static String get(String url) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
        try {
            c.setConnectTimeout(TIMEOUT_MS);
            c.setReadTimeout(TIMEOUT_MS);
            c.setRequestProperty("User-Agent", "farm-monitor/1.0");
            c.setInstanceFollowRedirects(true);
            int code = c.getResponseCode();
            if (code < 200 || code >= 300) throw new Exception("HTTP " + code);
            return readAll(c.getInputStream());
        } finally {
            c.disconnect();
        }
    }

    private static String readAll(InputStream in) throws Exception {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        byte[] buf = new byte[8192];
        int n;
        while ((n = in.read(buf)) > 0) out.write(buf, 0, n);
        in.close();
        return new String(out.toByteArray(), StandardCharsets.UTF_8);
    }

    /** Определяет настоящий публичный IP и провайдера. */
    public static Info detect(Context ctx) {
        Info info = new Info();
        info.connType = connType(ctx);
        try {
            info.ip = new JSONObject(get(IP_URL)).optString("ip", null);
        } catch (Exception e) {
            info.error = "Не удалось определить IP: " + e.getMessage();
            return info;
        }
        try {
            JSONObject meta = new JSONObject(get(String.format(META_URL, info.ip)));
            info.org = meta.optString("org", null);
            if (info.org == null || info.org.isEmpty()) info.org = meta.optString("asn", null);
            info.country = meta.optString("country_name", null);
        } catch (Exception ignored) {
            // Провайдер необязателен — панель разберётся и без него.
        }
        return info;
    }

    /** Wi-Fi, мобильные данные или Ethernet — по реальному активному транспорту. */
    public static String connType(Context ctx) {
        ConnectivityManager cm = (ConnectivityManager) ctx.getSystemService(Context.CONNECTIVITY_SERVICE);
        if (cm == null) return "unknown";
        Network net = cm.getActiveNetwork();
        if (net == null) return "offline";
        NetworkCapabilities cap = cm.getNetworkCapabilities(net);
        if (cap == null) return "unknown";
        if (cap.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR)) return "cellular";
        if (cap.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)) return "wifi";
        if (cap.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET)) return "ethernet";
        return "unknown";
    }

    /** Отправляет честный отчёт в панель. Возвращает null при успехе, иначе текст ошибки. */
    public static String report(String server, String deviceId, String name,
                                Info info, long bytesShared) {
        if (server == null || server.trim().isEmpty()) return "Не указан адрес панели";
        String base = server.trim();
        if (!base.startsWith("http://") && !base.startsWith("https://")) base = "http://" + base;
        while (base.endsWith("/")) base = base.substring(0, base.length() - 1);

        try {
            JSONObject payload = new JSONObject();
            payload.put("device_id", deviceId);
            payload.put("name", name);
            payload.put("public_ip", info.ip);
            payload.put("conn_type", info.connType);
            payload.put("org", info.org);
            payload.put("country", info.country);
            payload.put("bytes_shared", bytesShared);

            HttpURLConnection c = (HttpURLConnection) new URL(base + "/api/report").openConnection();
            try {
                c.setConnectTimeout(TIMEOUT_MS);
                c.setReadTimeout(TIMEOUT_MS);
                c.setDoOutput(true);
                c.setRequestMethod("POST");
                c.setRequestProperty("Content-Type", "application/json");
                byte[] body = payload.toString().getBytes(StandardCharsets.UTF_8);
                try (OutputStream os = c.getOutputStream()) {
                    os.write(body);
                }
                int code = c.getResponseCode();
                if (code < 200 || code >= 300) return "Панель ответила кодом " + code;
                c.getInputStream().close();
                return null;
            } finally {
                c.disconnect();
            }
        } catch (Exception e) {
            return e.getMessage();
        }
    }
}
