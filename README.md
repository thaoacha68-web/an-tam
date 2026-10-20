# An Tâm — nền tảng khám chữa bệnh trực tuyến

Ứng dụng web tiếng Việt có frontend độc lập và REST API Python/SQLite. Hỗ trợ ba vai trò bệnh nhân, bác sĩ và quản trị viên.

## Chạy nhanh

Yêu cầu Python 3.10+. Có thể nhấp đúp `start-local.bat`, hoặc chạy từ thư mục dự án:

```powershell
python backend/server.py
```

Mở http://localhost:8000. Dữ liệu khởi tạo lưu tại `data/clinic.db` (tạo tự động).

Không mở trực tiếp `frontend/index.html` bằng `file://`. Nếu dùng VS Code Live Server (ví dụ `localhost:5500`), vẫn phải chạy riêng `python backend/server.py`; frontend sẽ tự gửi yêu cầu API đến `localhost:8000`. Khi đăng nhập gặp lỗi kết nối, hãy kiểm tra cửa sổ `server.py` còn chạy.

## Tài khoản mẫu

| Vai trò | Email | Mật khẩu |
| --- | --- | --- |
| Quản trị | admin@antam.vn | Admin@123 |
| Bác sĩ | doctor@antam.vn | Doctor@123 |
| Bệnh nhân | patient@antam.vn | Patient@123 |

## API

REST API nằm dưới `/api`; `GET /api/health` là health check. Bearer token được cấp khi đăng nhập. Các nhóm API gồm auth, doctors, appointments, records, admin/users, admin/catalog, admin/dashboard và admin/observability.

## Triển khai

`Dockerfile`, `docker-compose.yml` và `deploy/` cung cấp cấu hình tham khảo cho Nginx, Prometheus, Grafana và Loki. Đổi mật khẩu mẫu, `APP_SECRET`, bật HTTPS và dùng secret manager trước khi triển khai công khai. Phần telemetry mẫu chỉ theo dõi ứng dụng/API; không thu thập hay ghi log nội dung bệnh án.

## Phạm vi bảo mật

Đây là nền tảng mẫu để phát triển, chưa được thẩm định cho dữ liệu y tế thực tế. Token lưu trong bộ nhớ tiến trình, SQLite phù hợp demo đơn máy; cần chuyển sang session/token an toàn, database production, backup và quy trình tuân thủ trước khi đưa vào vận hành thật.

## Chạy hệ thống bằng Docker Compose

### Yêu cầu

- Docker Desktop đang hoạt động và sử dụng Linux containers.
- Có file `.env` chứa cấu hình triển khai.
- Nếu chưa có `.env`, sao chép từ `.env.example` rồi điền mật khẩu.
- Không đưa `.env` lên GitHub.

### Khởi động

Chạy từ thư mục gốc của dự án:

```powershell
docker compose -f docker-compose.yml -f compose.windows.yml -f compose.logs.yml -f compose.hardening.yml -f compose.monitoring.yml up -d --build
```

### Kiểm tra trạng thái

```powershell
docker compose -f docker-compose.yml -f compose.windows.yml -f compose.logs.yml -f compose.hardening.yml -f compose.monitoring.yml ps -a
```

### Địa chỉ truy cập

| Thành phần | Địa chỉ |
| --- | --- |
| Website An Tâm | http://localhost:8080 |
| pgAdmin | http://localhost:5050 |
| Grafana | http://localhost:3000 |
| Prometheus | http://localhost:9090 |
| cAdvisor | http://localhost:8081/containers/ |
### Dừng hệ thống

```powershell
docker compose -f docker-compose.yml -f compose.windows.yml -f compose.logs.yml -f compose.hardening.yml -f compose.monitoring.yml stop
```

Dữ liệu được giữ trong Docker volumes khi dùng lệnh stop.