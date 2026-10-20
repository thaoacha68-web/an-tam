# Triển khai Docker

`docker compose up --build` khởi chạy app, PostgreSQL, pgAdmin, Nginx, Prometheus, Grafana và Loki.

- Website: http://localhost:8080
- pgAdmin: http://localhost:5050 (đăng nhập bằng biến `PGADMIN_EMAIL` / `PGADMIN_PASSWORD`; server hostname `postgres`, port 5432, database/user `antam`)
- Grafana: http://localhost:3000 (mặc định `admin` / `admin`; đổi mật khẩu ngay lần đầu)
- Prometheus: http://localhost:9090
- Dashboard Grafana: `An Tâm / An Tâm · Tổng quan vận hành` (requests, lỗi API, latency, CPU/RAM node, PostgreSQL)

Đặt `POSTGRES_PASSWORD`, `PGADMIN_PASSWORD` và các thông tin xác thực triển khai qua biến môi trường (có thể sao chép `.env.example` thành `.env`). Cấu hình Nginx hiện là HTTP nội bộ/edge mẫu; hoàn thiện chứng chỉ TLS trước khi mở ra Internet. Prometheus có exporters cho PostgreSQL và máy chủ/container. Trên Docker Desktop, chỉ số node phản ánh môi trường Linux của Docker, không đại diện hoàn toàn cho Windows host. Loki đã provision datasource và panel LogQL nhưng chưa nhận log vì ứng dụng demo không ghi nội dung request/bệnh án ra log; hãy gắn Promtail/Alloy với pipeline lọc dữ liệu nhạy cảm nếu cần truy vấn log.
