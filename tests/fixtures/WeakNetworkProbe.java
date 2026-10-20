import java.io.*;
import java.net.*;

// Bounded HTTP traffic generated inside Android, without installing an application.
public class WeakNetworkProbe {
    public static void main(String[] args) throws Exception {
        String host = args[0];
        int port = Integer.parseInt(args[1]);
        int size = Integer.parseInt(args[2]);
        boolean upload = args[3].equals("upload");
        long start = System.nanoTime();
        Proxy proxy = args.length > 4
            ? new Proxy(Proxy.Type.SOCKS, new InetSocketAddress("10.0.2.2", Integer.parseInt(args[4])))
            : Proxy.NO_PROXY;
        try (Socket socket = new Socket(proxy)) {
            socket.connect(new InetSocketAddress(host, port), 15000);
            socket.setSoTimeout(30000);
            OutputStream output = socket.getOutputStream();
            String header = (upload ? "POST" : "GET") + " /" + size + " HTTP/1.1\r\nHost: "
                + host + ":" + port + "\r\nConnection: close\r\nContent-Length: "
                + (upload ? size : 0) + "\r\n\r\n";
            output.write(header.getBytes("US-ASCII"));
            byte[] buffer = new byte[8192];
            if (upload) {
                for (int sent = 0; sent < size;) {
                    int count = Math.min(buffer.length, size - sent);
                    output.write(buffer, 0, count);
                    sent += count;
                }
            }
            output.flush();
            InputStream input = new BufferedInputStream(socket.getInputStream());
            int received = 0;
            ByteArrayOutputStream firstLine = new ByteArrayOutputStream();
            int next;
            while ((next = input.read()) != -1 && next != '\n' && firstLine.size() < 512) firstLine.write(next);
            String status = firstLine.toString("US-ASCII");
            if (!status.startsWith("HTTP/1.0 200") && !status.startsWith("HTTP/1.1 200")) {
                throw new IOException("Unexpected HTTP status: " + status);
            }
            received = firstLine.size() + 1;
            int count;
            while ((count = input.read(buffer)) != -1) received += count;
            System.out.println("{\"elapsed_ms\":" + (System.nanoTime() - start) / 1000000.0
                + ",\"status\":200,\"received\":" + received + "}");
        }
    }
}
