# An Tâm — Hệ thống Quản lý Phòng khám / Bệnh viện

Bài tập lớn môn Triển khai và Quản trị Hệ thống Phần mềm.

- Sinh viên: Thào A Chà
- MSSV: DTC245200711
- Repository: https://github.com/thaoacha68-web/an-tam

An Tâm là ứng dụng web tiếng Việt với frontend HTML/CSS/JavaScript và REST API Python. Hệ thống hỗ trợ ba vai trò: bệnh nhân, bác sĩ và quản trị viên.

Ứng dụng sử dụng SQLite khi chạy local không có `DATABASE_URL`. Trong cấu hình Docker Compose, ứng dụng sử dụng PostgreSQL.

## 1. Chức năng chính

| Vai trò | Chức năng |
| --- | --- |
| Bệnh nhân | Tra cứu bác sĩ, đặt lịch và xem hồ sơ khám |
| Bác sĩ | Theo dõi lịch hẹn và quản lý hồ sơ khám theo quyền |
| Quản trị viên | Quản lý tài khoản, danh mục và thống kê hệ thống |

## 2. Thành phần triển khai

Hệ thống gồm 11 dịch vụ chạy bằng Docker Compose:

| Dịch vụ | Vai trò |
| --- | --- |
| app | Chạy ứng dụng và REST API Python |
| postgres | Lưu trữ dữ liệu PostgreSQL |
| pgadmin | Quản trị PostgreSQL qua giao diện web |
| nginx | Reverse proxy và HTTP security headers |
| prometheus | Thu thập metrics |
| grafana | Hiển thị dashboard và truy vấn log |
| cadvisor | Thu thập CPU/RAM theo container |
| node-exporter | Thu thập metrics môi trường Linux chạy Docker |
| postgres-exporter | Thu thập metrics PostgreSQL |
| loki | Lưu trữ và truy vấn log |
| promtail | Thu thập log Nginx và gửi về Loki |

Luồng truy cập website:

Trình duyệt → Nginx → app → PostgreSQL.

Prometheus thu thập metrics từ ứng dụng và các exporter. Grafana truy vấn Prometheus để hiển thị biểu đồ, đồng thời truy vấn Loki để xem log.

## 3. Yêu cầu môi trường

- Git.
- Docker Desktop đang hoạt động và sử dụng Linux containers.
- Docker Compose hỗ trợ các file cấu hình của dự án.
- PowerShell để chạy các lệnh trong hướng dẫn.
- Trình duyệt web.

Nếu chỉ chạy ứng dụng trực tiếp, cần Python 3.10 trở lên và các thư viện trong `backend/requirements.txt`.

## 4. Lấy mã nguồn

Chạy trong thư mục cha muốn lưu dự án:

```powershell
git clone https://github.com/thaoacha68-web/an-tam.git baithiketthuchocphan
cd baithiketthuchocphan
```

Nếu đã có dự án trên máy, chỉ cần mở PowerShell tại thư mục gốc của dự án.

## 5. Cấu hình môi trường

Tạo `.env` từ file mẫu nếu chưa tồn tại:

```powershell
if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
}
```

Mở `.env`:

```powershell
notepad .env
```

Điền giá trị cho các biến được sử dụng trong Compose, gồm:

```dotenv
POSTGRES_PASSWORD=replace-with-a-long-random-password
PGADMIN_EMAIL=admin@antam.vn
PGADMIN_PASSWORD=replace-with-another-long-random-password
```

Các giá trị trên là mẫu. Thay mật khẩu mẫu khi thiết lập môi trường mới.

Nếu hệ thống đã hoạt động, giữ nguyên `.env` đang sử dụng.

Không đưa `.env` hoặc mật khẩu thật lên GitHub. `.env.example` chỉ chứa giá trị mẫu.

Lưu ý: thay `POSTGRES_PASSWORD` trong `.env` không tự đổi mật khẩu role PostgreSQL nếu database đã được khởi tạo trong volume.

## 6. Khởi động toàn bộ hệ thống

Mở Docker Desktop và đợi Docker Engine hoạt động.

Chạy từ thư mục gốc của dự án:

```powershell
docker compose -p baithiketthuchocphan -f docker-compose.yml -f compose.windows.yml -f compose.logs.yml -f compose.hardening.yml -f compose.monitoring.yml up -d --build
```

Ý nghĩa các file:

| File | Nội dung |
| --- | --- |
| docker-compose.yml | Cấu hình cơ sở của hệ thống |
| compose.windows.yml | Điều chỉnh cấu hình cho môi trường Windows |
| compose.logs.yml | Bổ sung dịch vụ thu thập log |
| compose.hardening.yml | Gia cố quyền chạy ứng dụng |
| compose.monitoring.yml | Bổ sung cAdvisor và cấu hình giám sát container |

Tham số `-p baithiketthuchocphan` giữ tên project phù hợp với bộ lọc Promtail và tên container trong hướng dẫn.

## 7. Kiểm tra trạng thái

```powershell
docker compose -p baithiketthuchocphan -f docker-compose.yml -f compose.windows.yml -f compose.logs.yml -f compose.hardening.yml -f compose.monitoring.yml ps -a
```

Kết quả mong đợi:

- Có đủ 11 dịch vụ đang chạy.
- PostgreSQL hiển thị healthy.
- cAdvisor hiển thị healthy.
- Không có dịch vụ liên tục Restarting hoặc Exited.

Trạng thái healthy phụ thuộc healthcheck của từng dịch vụ.

## 8. Địa chỉ truy cập

| Thành phần | Địa chỉ |
| --- | --- |
| Website An Tâm | http://localhost:8080 |
| pgAdmin | http://localhost:5050 |
| Grafana | http://localhost:3000 |
| Prometheus | http://localhost:9090 |
| Prometheus Targets | http://localhost:9090/targets |
| cAdvisor | http://localhost:8081/containers/ |
| Loki readiness | http://localhost:3100/ready |

Endpoint Loki readiness trả về trạng thái sẵn sàng. Để xem và truy vấn log, sử dụng Grafana Explore.

Có thể mở các giao diện bằng PowerShell:

```powershell
Start-Process "http://localhost:8080"
Start-Process "http://localhost:5050"
Start-Process "http://localhost:3000"
Start-Process "http://localhost:9090/targets"
Start-Process "http://localhost:8081/containers/"
```

## 9. Tài khoản mẫu của ứng dụng

Các tài khoản dưới đây dành cho dữ liệu demo khởi tạo:

| Vai trò | Email | Mật khẩu |
| --- | --- | --- |
| Quản trị | admin@antam.vn | Admin@123 |
| Bác sĩ | doctor@antam.vn | Doctor@123 |
| Bệnh nhân | patient@antam.vn | Patient@123 |

Nếu đã thay đổi mật khẩu trong ứng dụng, sử dụng mật khẩu mới.

Tài khoản ứng dụng, pgAdmin và Grafana là các tài khoản riêng biệt.

## 10. Kết nối PostgreSQL bằng pgAdmin

1. Mở http://localhost:5050.
2. Đăng nhập bằng `PGADMIN_EMAIL` và `PGADMIN_PASSWORD` đã cấu hình.
3. Nhấp chuột phải vào Servers.
4. Chọn Register > Server.
5. Trong tab General, đặt Name là `An Tam PostgreSQL`.
6. Trong tab Connection, điền:

| Trường | Giá trị |
| --- | --- |
| Host name/address | postgres |
| Port | 5432 |
| Maintenance database | antam |
| Username | antam |
| Password | Mật khẩu PostgreSQL đã cấu hình |

7. Bấm Save.

Để xem dữ liệu:

Databases > antam > Schemas > public > Tables.

Nhấp chuột phải vào bảng rồi chọn View/Edit Data > All Rows.

Hostname `postgres` là tên dịch vụ Docker. Không thay bằng `localhost` khi kết nối từ container pgAdmin đến PostgreSQL.

## 11. Kiểm tra Prometheus

Mở http://localhost:9090/targets.

Bốn job cần hiển thị UP:

- antam-api
- postgres
- node
- cadvisor

Ô Filter by endpoint or labels trên trang Targets chỉ dùng để lọc danh sách.

Để chạy PromQL, mở trang Graph và nhập vào ô Expression.

### Kiểm tra trạng thái thu thập metrics

```promql
up
```

- Giá trị 1: scrape thành công.
- Giá trị 0: scrape thất bại.

### Kiểm tra kết nối exporter tới PostgreSQL

```promql
pg_up
```

Giá trị mong đợi là 1.

### Xem RAM working set của container theo MiB

```promql
sum by (name) (
  container_memory_working_set_bytes{job="cadvisor",name!=""}
) / 1024 / 1024
```

### Xem CPU container theo phần trăm một lõi

```promql
100 * sum by (name) (
  rate(container_cpu_usage_seconds_total{job="cadvisor",name!=""}[5m])
)
```

CPU 100% tương đương sử dụng một lõi và có thể vượt 100% khi dùng nhiều lõi.

Node exporter phản ánh môi trường Linux chạy Docker. cAdvisor cung cấp metrics theo từng container.

## 12. Xem dashboard Grafana

1. Mở http://localhost:3000.
2. Đăng nhập bằng tài khoản Grafana đã thiết lập.
3. Chọn Dashboards.
4. Mở thư mục An Tâm.
5. Chọn dashboard tổng quan hoặc dashboard giám sát container.

Các nội dung giám sát gồm:

- Số request và lỗi API.
- Độ trễ API trung bình.
- CPU/RAM môi trường Linux.
- Kết nối PostgreSQL.
- CPU/RAM theo container.
- Log Nginx.

Các datasource bên trong Grafana sử dụng địa chỉ:

| Datasource | Địa chỉ |
| --- | --- |
| Prometheus | http://prometheus:9090 |
| Loki | http://loki:3100 |

Dashboard được quản lý bằng file JSON trong thư mục `deploy/`. Cần lưu thay đổi vào file tương ứng để cấu hình trong Git khớp với môi trường triển khai.

## 13. Tạo log thử cho Loki

Chạy trong PowerShell:

```powershell
# Tạo 10 request kiểm tra sức khỏe API
1..10 | ForEach-Object {
    curl.exe -s -o NUL http://localhost:8080/api/health
}

# Tạo 5 request tới đường dẫn thử
1..5 | ForEach-Object {
    curl.exe -s -o NUL http://localhost:8080/loki-test-khong-ton-tai
}
```

Đợi khoảng 10 giây để log được chuyển tới Loki.

Cấu hình Promtail hiện chỉ thu thập log Nginx, lọc theo project `baithiketthuchocphan` và service `nginx`.

## 14. Truy vấn log trong Grafana

Mở Grafana > Explore.

- Chọn datasource Loki.
- Chọn chế độ Code.
- Chọn thời gian Last 15 minutes.
- Nhập từng truy vấn và bấm Run query.

### Truy vấn 1: xem toàn bộ log Nginx

```logql
{job="nginx"}
```

### Truy vấn 2: lọc request kiểm tra sức khỏe

```logql
{job="nginx"} |= "/api/health"
```

### Truy vấn 3: lọc đường dẫn thử

```logql
{job="nginx"} |= "/loki-test-khong-ton-tai"
```

### Truy vấn 4: đếm log trong cửa sổ 5 phút

```logql
sum(count_over_time({job="nginx"}[5m]))
```

Kết quả phụ thuộc thời gian truy vấn và lượng truy cập website. Cửa sổ 5 phút là cửa sổ trượt tại mỗi thời điểm đánh giá.

Kiểm tra Loki sẵn sàng:

```powershell
curl.exe http://localhost:3100/ready
```

Kết quả mong đợi là `ready`.

## 15. Kiểm tra hardening

Bốn biện pháp đã áp dụng:

| Biện pháp | Cấu hình hoặc kết quả |
| --- | --- |
| App chạy non-root | UID/GID 10001 |
| Loại Linux capabilities | cap_drop: ALL |
| Hạn chế nhận thêm đặc quyền | no-new-privileges:true |
| HTTP security headers | nosniff, DENY, Referrer-Policy và CSP |

### Kiểm tra quyền chạy app

```powershell
docker exec baithiketthuchocphan-app-1 id
```

Kết quả mong đợi:

```text
uid=10001 gid=10001 groups=10001
```

### Kiểm tra capabilities và SecurityOpt

```powershell
docker inspect baithiketthuchocphan-app-1 --format '{{json .HostConfig.CapDrop}} {{json .HostConfig.SecurityOpt}}'
```

Kết quả mong đợi:

```text
["ALL"] ["no-new-privileges:true"]
```

### Kiểm tra cấu hình Nginx

```powershell
docker exec baithiketthuchocphan-nginx-1 nginx -t
```

Kết quả mong đợi có:

```text
syntax is ok
test is successful
```

### Kiểm tra HTTP headers

```powershell
curl.exe -I http://localhost:8080/
```

Phản hồi mong đợi có HTTP 200 và các header:

- X-Content-Type-Options: nosniff
- X-Frame-Options: DENY
- Referrer-Policy: strict-origin-when-cross-origin
- Content-Security-Policy

Các biện pháp trên giúp giảm rủi ro của ứng dụng. cAdvisor và Promtail có các quyền phục vụ giám sát nên cần đánh giá riêng khi triển khai ngoài môi trường học tập.

## 16. Xem log khi có lỗi

Xem log gần nhất của ứng dụng:

```powershell
docker logs --tail=80 baithiketthuchocphan-app-1
```

Xem log Nginx:

```powershell
docker logs --tail=80 baithiketthuchocphan-nginx-1
```

Xem log Promtail:

```powershell
docker logs --tail=80 baithiketthuchocphan-promtail-1
```

Xem log Loki:

```powershell
docker logs --tail=80 baithiketthuchocphan-loki-1
```

### Docker Desktop không hoạt động

Mở Docker Desktop và đợi Docker Engine sẵn sàng.

Kiểm tra:

```powershell
docker info
```

### Grafana hiển thị No data

- Kiểm tra khoảng thời gian đang chọn.
- Kiểm tra datasource.
- Kiểm tra Prometheus Targets.
- Với Loki, tạo request mới và dùng nhãn `job="nginx"`.

### Grafana gặp lỗi removeChild

Tắt dịch tự động của trình duyệt cho trang Grafana, tải lại trang rồi thử truy vấn.

### pgAdmin không kết nối được DB

- Kiểm tra PostgreSQL đang chạy.
- Dùng hostname `postgres`, cổng 5432.
- Dùng mật khẩu của tài khoản PostgreSQL đã tồn tại trong volume.

### Phiên đăng nhập ứng dụng hết hiệu lực

Token lưu trong bộ nhớ tiến trình. Sau khi app khởi động lại, có thể cần đăng nhập lại.

## 17. Dừng và chạy lại hệ thống

Dừng toàn bộ dịch vụ:

```powershell
docker compose -p baithiketthuchocphan -f docker-compose.yml -f compose.windows.yml -f compose.logs.yml -f compose.hardening.yml -f compose.monitoring.yml stop
```

Chạy lại:

```powershell
docker compose -p baithiketthuchocphan -f docker-compose.yml -f compose.windows.yml -f compose.logs.yml -f compose.hardening.yml -f compose.monitoring.yml up -d
```

Dữ liệu trong Docker volumes được giữ lại khi dùng `stop`.

Không dùng `down -v` nếu cần giữ dữ liệu và chưa sao lưu.

## 18. Chạy ứng dụng trực tiếp bằng Python

Cài thư viện:

```powershell
python -m pip install -r backend/requirements.txt
```

Chạy server:

```powershell
python backend/server.py
```

Có thể sử dụng `start-local.bat` nếu Python đã được cấu hình phù hợp trên máy.

Mở http://localhost:8000.

Khi không cấu hình `DATABASE_URL`, ứng dụng sử dụng SQLite tại `data/clinic.db`, được tạo tự động.

Không mở trực tiếp `frontend/index.html` bằng `file://`.

Nếu dùng VS Code Live Server, vẫn phải chạy riêng backend.

## 19. API

REST API nằm dưới `/api`.

Health check:

```text
GET /api/health
```

Các nhóm API:

- auth
- doctors
- appointments
- records
- admin/users
- admin/catalog
- admin/dashboard
- admin/observability

Ứng dụng cấp Bearer token khi đăng nhập.

## 20. Phạm vi bảo mật và hướng phát triển

Đây là dự án phục vụ học tập và demo, chưa được thẩm định để sử dụng với dữ liệu y tế thực tế.

Bản triển khai hiện sử dụng HTTP có security headers. Chưa xem HTTPS, phân tách nhiều network, giảm quyền DB, backup hoặc tính sẵn sàng cao là các kết quả đã hoàn thiện.

Các hướng phát triển:

- Bổ sung HTTPS.
- Tách tài khoản quản trị DB và tài khoản ứng dụng theo nguyên tắc tối thiểu quyền.
- Phân tách network theo chức năng.
- Giới hạn truy cập các cổng quản trị.
- Quản lý và luân chuyển mật khẩu.
- Hoàn thiện quản lý phiên đăng nhập.
- Thiết lập backup và kiểm tra phục hồi.
- Bổ sung cảnh báo giám sát.
- Tự động hóa kiểm tra và triển khai bằng CI/CD.

Không đưa mật khẩu thật, token hoặc dữ liệu bệnh án vào GitHub và ảnh minh chứng.