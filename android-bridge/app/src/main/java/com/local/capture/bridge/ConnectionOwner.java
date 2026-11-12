package com.local.capture.bridge;

import android.content.Context;
import android.net.ConnectivityManager;
import android.net.LocalServerSocket;
import android.net.LocalSocket;
import android.system.OsConstants;
import java.io.ByteArrayOutputStream;
import java.io.Closeable;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import org.json.JSONArray;
import org.json.JSONObject;

/** Private USB control channel; returns only flow ownership, never traffic content. */
final class ConnectionOwner implements Closeable {
    private final LocalServerSocket server;
    private final String token;
    private final Context context;
    private final int targetUid;
    private final int loginUid;
    private volatile boolean closed;
    private volatile LocalSocket active;

    ConnectionOwner(Context context, int targetUid, int loginUid) throws Exception {
        this.context = context;
        this.targetUid = targetUid;
        this.loginUid = loginUid;
        token = BridgeFiles.read(context, "routing-token").trim();
        if (!token.matches("[a-f0-9]{64}")) throw new IllegalArgumentException();
        byte[] digest = MessageDigest.getInstance("SHA-256").digest(token.getBytes(StandardCharsets.UTF_8));
        StringBuilder name = new StringBuilder("capture-owner-");
        for (byte value : digest) name.append(String.format(java.util.Locale.ROOT, "%02x", value & 255));
        server = new LocalServerSocket(name.toString());
        Thread thread = new Thread(this::serve, "capture-owner");
        thread.setDaemon(true);
        thread.start();
    }

    static String classify(int uid, int targetUid, int loginUid) {
        if (uid < 10000 || targetUid == loginUid) return "unknown";
        if (uid == targetUid) return "target";
        if (uid == loginUid) return "login";
        return "unknown";
    }

    static String proof(String token, String message) throws Exception {
        Mac mac = Mac.getInstance("HmacSHA256");
        mac.init(new SecretKeySpec(token.getBytes(StandardCharsets.UTF_8), "HmacSHA256"));
        StringBuilder result = new StringBuilder();
        for (byte value : mac.doFinal(message.getBytes(StandardCharsets.UTF_8))) {
            result.append(String.format(java.util.Locale.ROOT, "%02x", value & 255));
        }
        return result.toString();
    }

    private InetSocketAddress address(JSONArray value) throws Exception {
        String ip = value.getString(0);
        int port = value.getInt(1);
        if (!ip.matches("[0-9a-fA-F:.]+") || port < 1 || port > 65535) throw new IllegalArgumentException();
        return new InetSocketAddress(InetAddress.getByName(ip), port);
    }

    private void serve() {
        while (!closed) {
            try (LocalSocket socket = server.accept()) {
                active = socket;
                socket.setSoTimeout(1500);
                ByteArrayOutputStream bytes = new ByteArrayOutputStream();
                int b;
                while ((b = socket.getInputStream().read()) != -1 && b != '\n') {
                    if (bytes.size() >= 1024) throw new IllegalArgumentException();
                    bytes.write(b);
                }
                JSONObject request = new JSONObject(bytes.toString("UTF-8"));
                String nonce = request.getString("nonce");
                if (!nonce.matches("[a-f0-9]{32}")) continue;
                JSONArray local = request.getJSONArray("local"), remote = request.getJSONArray("remote");
                InetSocketAddress localAddress = address(local), remoteAddress = address(remote);
                String message = nonce + "\n" + local.getString(0) + "\n" + local.getInt(1)
                        + "\n" + remote.getString(0) + "\n" + remote.getInt(1);
                if (!MessageDigest.isEqual(proof(token, "query\n" + message).getBytes(StandardCharsets.UTF_8),
                        request.getString("proof").getBytes(StandardCharsets.UTF_8))) continue;
                String role = "unknown";
                if (!BridgeFiles.lease(context).isBlank()) {
                    ConnectivityManager manager = context.getSystemService(ConnectivityManager.class);
                    int uid = manager.getConnectionOwnerUid(OsConstants.IPPROTO_TCP,
                            localAddress, remoteAddress);
                    role = classify(uid, targetUid, loginUid);
                }
                String reply = new JSONObject().put("role", role)
                        .put("proof", proof(token, "reply\n" + message + "\n" + role)).toString();
                socket.getOutputStream().write((reply + "\n").getBytes(StandardCharsets.UTF_8));
            } catch (Exception ignored) {
                // A missing permission, stale tuple or expired lease must never grant capture.
            } finally { active = null; }
        }
    }

    @Override public void close() {
        closed = true;
        try { if (active != null) active.close(); } catch (Exception ignored) { }
        try { server.close(); } catch (Exception ignored) { }
    }
}
