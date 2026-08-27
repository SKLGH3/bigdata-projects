package com.asxy.flume;

import com.alibaba.fastjson.JSONObject;
import com.zaxxer.hikari.HikariConfig;
import com.zaxxer.hikari.HikariDataSource;
import org.apache.flume.*;
import org.apache.flume.conf.Configurable;
import org.apache.flume.sink.AbstractSink;

import java.nio.charset.StandardCharsets;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.util.ArrayList;
import java.util.List;

/**
 * Flume自定义Sink - 将用户行为日志写入Phoenix(HBase)
 */
public class PhoenixSink extends AbstractSink implements Configurable {

    private int batchSize = 100;
    private int maxRetries = 3;
    private HikariDataSource dataSource;
    private List<JSONObject> batchBuffer = new ArrayList<>();

    @Override
    public void configure(Context context) {
        this.batchSize = context.getInteger("batchSize", 100);
        this.maxRetries = context.getInteger("maxRetries", 3);
        System.out.println("[PhoenixSink] 配置加载: batchSize=" + batchSize + ", maxRetries=" + maxRetries);
    }

    @Override
    public void start() {
        try {
            HikariConfig config = new HikariConfig();
            config.setJdbcUrl("jdbc:phoenix:hadoop142,hadoop143,hadoop144:2181");
            config.setDriverClassName("org.apache.phoenix.jdbc.PhoenixDriver");
            config.setMaximumPoolSize(10);
            config.setMinimumIdle(2);
            config.setConnectionTimeout(30000);
            config.setIdleTimeout(600000);
            config.setMaxLifetime(1800000);

            dataSource = new HikariDataSource(config);
            System.out.println("[PhoenixSink] 连接池启动成功");
        } catch (Exception e) {
            throw new RuntimeException("[PhoenixSink] 连接池初始化失败", e);
        }
        super.start();
    }

    @Override
    public Status process() throws EventDeliveryException {
        Channel channel = getChannel();
        Transaction tx = channel.getTransaction();
        tx.begin();

        Connection conn = null;
        PreparedStatement ps = null;

        try {
            int count = 0;
            while (count < batchSize) {
                Event event = channel.take();
                if (event == null) break;
                String body = new String(event.getBody(), StandardCharsets.UTF_8);
                batchBuffer.add(JSONObject.parseObject(body));
                count++;
            }

            if (batchBuffer.isEmpty()) {
                tx.commit();
                return Status.BACKOFF;
            }

            conn = dataSource.getConnection();
            conn.setAutoCommit(false);
            ps = conn.prepareStatement(
                "UPSERT INTO USER_ACTION (ID, USER_NAME, ACTION, EVENT_TIME, IP, DEVICE, DURATION, PAGE_URL) " +
                "VALUES(?,?,?,?,?,?,?,?)"
            );

            executeWithRetry(conn, ps);

            tx.commit();
            System.out.println("[PhoenixSink] 批量写入 " + batchBuffer.size() + " 条数据成功");
            batchBuffer.clear();

            return Status.READY;

        } catch (Exception e) {
            try { tx.rollback(); } catch (Exception ignore) {}
            try { if (conn != null) conn.rollback(); } catch (Exception ignore) {}
            batchBuffer.clear();
            throw new EventDeliveryException("[PhoenixSink] 写入失败", e);
        } finally {
            try { if (ps != null) ps.close(); } catch (Exception ignore) {}
            try { if (conn != null) conn.close(); } catch (Exception ignore) {}
            try { tx.close(); } catch (Exception ignore) {}
        }
    }

    private void executeWithRetry(Connection conn, PreparedStatement ps) throws Exception {
        int retryCount = 0;
        while (retryCount < maxRetries) {
            try {
                for (JSONObject json : batchBuffer) {
                    ps.setString(1, json.getString("id"));
                    ps.setString(2, json.getString("user"));
                    ps.setString(3, json.getString("action"));
                    ps.setString(4, json.getString("time"));
                    ps.setString(5, json.getString("ip"));
                    ps.setString(6, json.getString("device"));
                    ps.setString(7, json.getString("duration"));
                    ps.setString(8, json.getString("page"));
                    ps.addBatch();
                }
                ps.executeBatch();
                conn.commit();
                return;
            } catch (Exception e) {
                retryCount++;
                System.err.println("[PhoenixSink] 批量写入失败，第" + retryCount + "次重试...");
                if (retryCount >= maxRetries) {
                    throw e;
                }
                Thread.sleep(1000 * retryCount);
            }
        }
    }

    @Override
    public void stop() {
        try {
            if (!batchBuffer.isEmpty()) {
                Connection conn = dataSource.getConnection();
                conn.setAutoCommit(false);
                PreparedStatement ps = conn.prepareStatement(
                    "UPSERT INTO USER_ACTION (ID, USER_NAME, ACTION, EVENT_TIME, IP, DEVICE, DURATION, PAGE_URL) " +
                    "VALUES(?,?,?,?,?,?,?,?)"
                );
                for (JSONObject json : batchBuffer) {
                    ps.setString(1, json.getString("id"));
                    ps.setString(2, json.getString("user"));
                    ps.setString(3, json.getString("action"));
                    ps.setString(4, json.getString("time"));
                    ps.setString(5, json.getString("ip"));
                    ps.setString(6, json.getString("device"));
                    ps.setString(7, json.getString("duration"));
                    ps.setString(8, json.getString("page"));
                    ps.addBatch();
                }
                ps.executeBatch();
                conn.commit();
                System.out.println("[PhoenixSink] 关闭前刷出 " + batchBuffer.size() + " 条数据");
                ps.close();
                conn.close();
                batchBuffer.clear();
            }

            if (dataSource != null && !dataSource.isClosed()) {
                dataSource.close();
                System.out.println("[PhoenixSink] 连接池已关闭");
            }
        } catch (Exception e) {
            e.printStackTrace();
        }
        super.stop();
    }
}
