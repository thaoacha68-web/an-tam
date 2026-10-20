"""An Tam clinic demo API. Python standard library only."""
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import hashlib, hmac, json, os, secrets, sqlite3, time
from datetime import date, timedelta

DATABASE_URL = os.environ.get('DATABASE_URL', '')
if DATABASE_URL:
    import psycopg
    from psycopg.rows import dict_row
    INTEGRITY_ERROR = psycopg.IntegrityError
else: INTEGRITY_ERROR = sqlite3.IntegrityError

class PgConnection:
    """Small compatibility layer so local SQLite and deployed PostgreSQL share the API."""
    def __init__(self, raw): self.raw=raw
    def __enter__(self): self.raw.__enter__(); return self
    def __exit__(self,*a): return self.raw.__exit__(*a)
    def execute(self,sql,args=()): return self.raw.execute(sql.replace('?','%s'),args)
    def executescript(self,sql):
        for statement in sql.split(';'):
            if statement.strip(): self.raw.execute(statement)

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / 'data' / 'clinic.db'
TOKENS = {}
METRICS = {'requests': 0, 'errors': 0, 'latencies': []}

def connect():
    if DATABASE_URL: return PgConnection(psycopg.connect(DATABASE_URL, row_factory=dict_row))
    DB.parent.mkdir(exist_ok=True)
    db = sqlite3.connect(DB); db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    return db

def pw_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    return salt + '$' + hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 180000).hex()

def verify(password, stored):
    salt, digest = stored.split('$', 1)
    return hmac.compare_digest(pw_hash(password, salt).split('$', 1)[1], digest)

def init_db():
    with connect() as d:
        if DATABASE_URL:
            d.executescript('''
            CREATE TABLE IF NOT EXISTS users(id BIGSERIAL PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, phone TEXT DEFAULT '', role TEXT NOT NULL, specialty TEXT DEFAULT '', bio TEXT DEFAULT '', medical_history TEXT DEFAULT '', fee INTEGER DEFAULT 0, password TEXT NOT NULL, active BOOLEAN DEFAULT TRUE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS appointments(id BIGSERIAL PRIMARY KEY, patient_id BIGINT REFERENCES users(id), doctor_id BIGINT REFERENCES users(id), date DATE NOT NULL, slot TEXT NOT NULL, symptoms TEXT DEFAULT '', status TEXT DEFAULT 'pending', cancel_reason TEXT DEFAULT '', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
            CREATE UNIQUE INDEX IF NOT EXISTS active_doctor_slot ON appointments(doctor_id,date,slot) WHERE status IN ('pending','confirmed');
            CREATE TABLE IF NOT EXISTS records(id BIGSERIAL PRIMARY KEY, appointment_id BIGINT REFERENCES appointments(id), patient_id BIGINT REFERENCES users(id), doctor_id BIGINT REFERENCES users(id), diagnosis TEXT NOT NULL, symptoms TEXT DEFAULT '', conclusion TEXT DEFAULT '', prescription TEXT DEFAULT '[]', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS availability(id BIGSERIAL PRIMARY KEY, doctor_id BIGINT REFERENCES users(id) ON DELETE CASCADE, weekday INTEGER NOT NULL, slot TEXT NOT NULL, UNIQUE(doctor_id,weekday,slot));
            CREATE TABLE IF NOT EXISTS catalog(id BIGSERIAL PRIMARY KEY, kind TEXT NOT NULL, name TEXT NOT NULL, description TEXT DEFAULT '', UNIQUE(kind,name));
            CREATE TABLE IF NOT EXISTS rooms(id BIGSERIAL PRIMARY KEY, name TEXT NOT NULL UNIQUE, location TEXT DEFAULT '', capacity INTEGER DEFAULT 1, doctor_id BIGINT REFERENCES users(id) ON DELETE SET NULL, active BOOLEAN DEFAULT TRUE);
            CREATE TABLE IF NOT EXISTS support_messages(id BIGSERIAL PRIMARY KEY, user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE, sender_role TEXT NOT NULL, message TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
            ALTER TABLE appointments ADD COLUMN IF NOT EXISTS room_id BIGINT REFERENCES rooms(id) ON DELETE SET NULL;
            ALTER TABLE users ADD COLUMN IF NOT EXISTS medical_history TEXT DEFAULT '';
            ''')
        else: d.executescript('''
            CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, phone TEXT DEFAULT '', role TEXT NOT NULL, specialty TEXT DEFAULT '', bio TEXT DEFAULT '', medical_history TEXT DEFAULT '', fee INTEGER DEFAULT 0, password TEXT NOT NULL, active INTEGER DEFAULT 1, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS appointments(id INTEGER PRIMARY KEY, patient_id INTEGER REFERENCES users(id), doctor_id INTEGER REFERENCES users(id), date TEXT NOT NULL, slot TEXT NOT NULL, symptoms TEXT DEFAULT '', status TEXT DEFAULT 'pending', cancel_reason TEXT DEFAULT '', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE UNIQUE INDEX IF NOT EXISTS active_doctor_slot ON appointments(doctor_id,date,slot) WHERE status IN ('pending','confirmed');
            CREATE TABLE IF NOT EXISTS records(id INTEGER PRIMARY KEY, appointment_id INTEGER REFERENCES appointments(id), patient_id INTEGER REFERENCES users(id), doctor_id INTEGER REFERENCES users(id), diagnosis TEXT NOT NULL, symptoms TEXT DEFAULT '', conclusion TEXT DEFAULT '', prescription TEXT DEFAULT '[]', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS availability(id INTEGER PRIMARY KEY, doctor_id INTEGER REFERENCES users(id) ON DELETE CASCADE, weekday INTEGER NOT NULL, slot TEXT NOT NULL, UNIQUE(doctor_id,weekday,slot));
            CREATE TABLE IF NOT EXISTS catalog(id INTEGER PRIMARY KEY, kind TEXT NOT NULL, name TEXT NOT NULL, description TEXT DEFAULT '', UNIQUE(kind,name));
            CREATE TABLE IF NOT EXISTS rooms(id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, location TEXT DEFAULT '', capacity INTEGER DEFAULT 1, doctor_id INTEGER REFERENCES users(id) ON DELETE SET NULL, active INTEGER DEFAULT 1);
            CREATE TABLE IF NOT EXISTS support_messages(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, sender_role TEXT NOT NULL, message TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            ''')
        if not DATABASE_URL:
            if 'medical_history' not in [x['name'] for x in d.execute('PRAGMA table_info(users)')]: d.execute("ALTER TABLE users ADD COLUMN medical_history TEXT DEFAULT ''")
            if 'room_id' not in [x['name'] for x in d.execute('PRAGMA table_info(appointments)')]: d.execute('ALTER TABLE appointments ADD COLUMN room_id INTEGER REFERENCES rooms(id) ON DELETE SET NULL')
        users = [
          ('Quản trị viên','admin@antam.vn','0901000000','admin','','',0,'Admin@123'),
          ('BS. Nguyễn Minh Anh','doctor@antam.vn','0902000001','doctor','Tim mạch','12 năm kinh nghiệm · Đại học Y Hà Nội',350000,'Doctor@123'),
          ('BS. Trần Hoàng Nam','nam@antam.vn','0902000002','doctor','Nội tổng quát','10 năm kinh nghiệm · Bệnh viện Bạch Mai',300000,'Doctor@123'),
          ('BS. Lê Thu Hà','ha@antam.vn','0902000003','doctor','Nhi khoa','8 năm kinh nghiệm · Đại học Y Dược TP.HCM',280000,'Doctor@123'),
          ('Nguyễn Thị Minh','patient@antam.vn','0912000000','patient','','',0,'Patient@123')]
        for name,email,phone,role,spec,bio,fee,password in users:
            if not d.execute('SELECT id FROM users WHERE email=?',(email,)).fetchone():
                d.execute('INSERT INTO users(name,email,phone,role,specialty,bio,fee,password) VALUES(?,?,?,?,?,?,?,?)',(name,email,phone,role,spec,bio,fee,pw_hash(password)))
        for doctor in d.execute("SELECT id FROM users WHERE role='doctor'").fetchall():
            if not d.execute('SELECT id FROM availability WHERE doctor_id=? LIMIT 1',(doctor['id'],)).fetchone():
                for weekday in range(6):
                    for slot in ['09:00','10:00','11:00','14:00','15:00','16:00']: d.execute('INSERT INTO availability(doctor_id,weekday,slot) VALUES(?,?,?)',(doctor['id'],weekday,slot))
        for kind, names in [('specialty',['Tim mạch','Nội tổng quát','Nhi khoa','Da liễu','Thần kinh']),('medicine',['Paracetamol 500mg','Vitamin C 500mg','Amoxicillin 500mg','Loratadin 10mg']),('clinic',['Phòng khám An Tâm · Cơ sở 1','Phòng khám An Tâm · Cơ sở 2'])]:
            for name in names: d.execute('INSERT INTO catalog(kind,name) VALUES(?,?) ON CONFLICT(kind,name) DO NOTHING',(kind,name))
        patient=d.execute("SELECT id FROM users WHERE email='patient@antam.vn'").fetchone()['id']
        doc=d.execute("SELECT id FROM users WHERE email='doctor@antam.vn'").fetchone()['id']
        if not d.execute('SELECT id FROM appointments LIMIT 1').fetchone():
            d.execute("INSERT INTO appointments(patient_id,doctor_id,date,slot,symptoms,status) VALUES(?,?,?,'09:00','Khám sức khỏe định kỳ','confirmed')",(patient,doc,(date.today()+timedelta(days=1)).isoformat()))

def row(r): return dict(r) if r else None
def rows(rs): return [dict(r) for r in rs]

class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*a,**kw): super().__init__(*a,directory=str(ROOT / 'frontend'),**kw)
    def log_message(self,*args): pass
    def send_json(self, code, data):
        b=json.dumps(data,ensure_ascii=False,default=str).encode(); self.send_response(code); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Content-Length',str(len(b))); self.send_header('Access-Control-Allow-Origin','*'); self.send_header('Access-Control-Allow-Headers','Content-Type, Authorization'); self.send_header('Access-Control-Allow-Methods','GET, POST, PUT, DELETE, OPTIONS'); self.end_headers(); self.wfile.write(b)
    def body(self):
        n=int(self.headers.get('Content-Length',0)); return json.loads(self.rfile.read(n) or b'{}')
    def auth(self, roles=None):
        token=self.headers.get('Authorization','').replace('Bearer ',''); user=TOKENS.get(token)
        if not user: raise ValueError('Vui lòng đăng nhập để tiếp tục.')
        with connect() as d: fresh=row(d.execute('SELECT id,name,email,phone,role,specialty,bio,medical_history,fee,active FROM users WHERE id=?',(user['id'],)).fetchone())
        if not fresh or not fresh['active']: raise ValueError('Tài khoản đã bị khóa.')
        if roles and fresh['role'] not in roles: raise PermissionError('Bạn không có quyền thực hiện thao tác này.')
        return fresh
    def do_OPTIONS(self): self.send_response(204); self.send_header('Access-Control-Allow-Origin','*'); self.send_header('Access-Control-Allow-Headers','Content-Type, Authorization'); self.send_header('Access-Control-Allow-Methods','GET, POST, PUT, DELETE, OPTIONS'); self.send_header('Access-Control-Max-Age','600'); self.end_headers()
    def do_GET(self): self.route('GET')
    def do_POST(self): self.route('POST')
    def do_PUT(self): self.route('PUT')
    def do_DELETE(self): self.route('DELETE')
    def route(self, method):
        started=time.time(); METRICS['requests']+=1
        try:
            path=urlparse(self.path).path; q=parse_qs(urlparse(self.path).query); data=self.body() if method in ('POST','PUT') else {}
            if method=='GET' and not path.startswith('/api/') and path!='/metrics': return SimpleHTTPRequestHandler.do_GET(self)
            if path=='/metrics' and method=='GET':
                lat=METRICS['latencies'][-100:]; avg=sum(lat)/max(1,len(lat))
                body=f'# HELP antam_http_requests_total Requests handled by the API\n# TYPE antam_http_requests_total counter\nantam_http_requests_total {METRICS["requests"]}\n# HELP antam_http_errors_total API errors\n# TYPE antam_http_errors_total counter\nantam_http_errors_total {METRICS["errors"]}\n# HELP antam_http_latency_avg_ms Average API latency in milliseconds\n# TYPE antam_http_latency_avg_ms gauge\nantam_http_latency_avg_ms {avg:.2f}\n'
                raw=body.encode(); self.send_response(200); self.send_header('Content-Type','text/plain; version=0.0.4'); self.send_header('Content-Length',str(len(raw))); self.end_headers(); self.wfile.write(raw); return
            with connect() as d:
                if path=='/api/health': return self.send_json(200,{'status':'ok','service':'antam-api','timestamp':int(time.time())})
                if path=='/api/auth/register' and method=='POST':
                    if not data.get('name') or not data.get('email') or len(data.get('password',''))<8: return self.send_json(400,{'error':'Vui lòng nhập đủ thông tin và mật khẩu tối thiểu 8 ký tự.'})
                    try: cur=d.execute("INSERT INTO users(name,email,phone,role,password) VALUES(?,?,?,'patient',?) RETURNING id",(data['name'],data['email'].lower(),data.get('phone',''),pw_hash(data['password'])))
                    except INTEGRITY_ERROR: return self.send_json(409,{'error':'Email này đã được đăng ký.'})
                    u=row(d.execute('SELECT id,name,email,phone,role,specialty,bio,medical_history,fee,active FROM users WHERE id=?',(cur.fetchone()['id'],)).fetchone()); token=secrets.token_urlsafe(32); TOKENS[token]=u; return self.send_json(201,{'token':token,'user':u})
                if path=='/api/auth/login' and method=='POST':
                    u=row(d.execute('SELECT * FROM users WHERE email=?',(data.get('email','').lower(),)).fetchone())
                    if not u or not verify(data.get('password',''),u['password']): return self.send_json(401,{'error':'Email hoặc mật khẩu không chính xác.'})
                    if not u['active']: return self.send_json(403,{'error':'Tài khoản đã bị khóa. Vui lòng liên hệ quản trị viên.'})
                    token=secrets.token_urlsafe(32); clean={k:u[k] for k in ('id','name','email','phone','role','specialty','bio','medical_history','fee','active')}; TOKENS[token]=clean; return self.send_json(200,{'token':token,'user':clean})
                user=self.auth() if path!='/api/doctors' and not path.startswith('/api/doctors/') else None
                if path=='/api/auth/me': return self.send_json(200,{'user':user})
                if path=='/api/auth/logout':
                    TOKENS.pop(self.headers.get('Authorization','').replace('Bearer ',''),None); return self.send_json(200,{'ok':True})
                if path=='/api/doctors':
                    term=q.get('q',[''])[0].lower(); spec=q.get('specialty',[''])[0]
                    sql="SELECT id,name,specialty,bio,fee FROM users WHERE role='doctor' AND active"; args=[]
                    if term: sql+=' AND (lower(name) LIKE ? OR lower(specialty) LIKE ?)'; args += [f'%{term}%',f'%{term}%']
                    if spec: sql+=' AND specialty=?'; args.append(spec)
                    doctors=rows(d.execute(sql+' ORDER BY name',args))
                    date_filter=q.get('date',[''])[0]
                    try: weekday=date.fromisoformat(date_filter).weekday() if date_filter else None
                    except ValueError: weekday=None
                    for doctor in doctors:
                        av_sql='SELECT DISTINCT slot FROM availability WHERE doctor_id=?'; av_args=[doctor['id']]
                        if weekday is not None: av_sql+=' AND weekday=?'; av_args.append(weekday)
                        doctor['slots']=[x['slot'] for x in d.execute(av_sql+' ORDER BY slot',av_args)]
                    return self.send_json(200,{'doctors':doctors,'specialties':[x['name'] for x in d.execute("SELECT name FROM catalog WHERE kind='specialty' ORDER BY name")]})
                if path=='/api/appointments':
                    room_select=',rm.name room_name,rm.location room_location'
                    if user['role']=='patient': sql='SELECT a.*,p.name patient_name,dr.name doctor_name,dr.specialty,dr.fee'+room_select+' FROM appointments a JOIN users p ON p.id=a.patient_id JOIN users dr ON dr.id=a.doctor_id LEFT JOIN rooms rm ON rm.id=a.room_id WHERE a.patient_id=? ORDER BY a.date DESC,a.slot'; args=[user['id']]
                    elif user['role']=='doctor': sql='SELECT a.*,p.name patient_name,p.phone patient_phone,p.medical_history patient_medical_history,dr.name doctor_name,dr.specialty'+room_select+' FROM appointments a JOIN users p ON p.id=a.patient_id JOIN users dr ON dr.id=a.doctor_id LEFT JOIN rooms rm ON rm.id=a.room_id WHERE a.doctor_id=? ORDER BY a.date,a.slot'; args=[user['id']]
                    else: sql='SELECT a.*,p.name patient_name,dr.name doctor_name,dr.specialty'+room_select+' FROM appointments a JOIN users p ON p.id=a.patient_id JOIN users dr ON dr.id=a.doctor_id LEFT JOIN rooms rm ON rm.id=a.room_id ORDER BY a.date DESC'; args=[]
                    return self.send_json(200,{'appointments':rows(d.execute(sql,args))})
                if path=='/api/availability':
                    if user['role']!='doctor': return self.send_json(403,{'error':'Chỉ bác sĩ mới được xem lịch làm việc.'})
                    return self.send_json(200,{'availability':rows(d.execute('SELECT weekday,slot FROM availability WHERE doctor_id=? ORDER BY weekday,slot',(user['id'],)))})
                if path=='/api/records':
                    if user['role']=='patient': rs=d.execute('SELECT r.*,dr.name doctor_name,dr.specialty FROM records r JOIN users dr ON dr.id=r.doctor_id WHERE r.patient_id=? ORDER BY r.created_at DESC',(user['id'],))
                    elif user['role']=='doctor': rs=d.execute('SELECT r.*,p.name patient_name,dr.name doctor_name FROM records r JOIN users p ON p.id=r.patient_id JOIN users dr ON dr.id=r.doctor_id WHERE r.doctor_id=? ORDER BY r.created_at DESC',(user['id'],))
                    else: rs=d.execute('SELECT r.*,p.name patient_name,dr.name doctor_name FROM records r JOIN users p ON p.id=r.patient_id JOIN users dr ON dr.id=r.doctor_id ORDER BY r.created_at DESC')
                    return self.send_json(200,{'records':[dict(x, prescription=json.loads(x['prescription'] or '[]')) for x in rs]})
                if path=='/api/support/messages':
                    return self.send_json(200,{'messages':rows(d.execute('SELECT id,user_id,sender_role,message,created_at FROM support_messages WHERE user_id=? ORDER BY created_at,id',(user['id'],)))})
                if path=='/api/admin/dashboard':
                    self.auth(['admin']); counts={k:d.execute(sql).fetchone()['count'] for k,sql in {'appointments':'SELECT count(*) AS count FROM appointments','patients':"SELECT count(*) AS count FROM users WHERE role='patient'",'doctors':"SELECT count(*) AS count FROM users WHERE role='doctor'",'pending':"SELECT count(*) AS count FROM appointments WHERE status='pending'"}.items()}
                    return self.send_json(200,{'counts':counts,'specialties':rows(d.execute("SELECT specialty name,count(*) value FROM appointments JOIN users ON users.id=appointments.doctor_id GROUP BY specialty ORDER BY value DESC")),'recent':rows(d.execute('SELECT a.id,a.date,a.status,p.name patient_name,dr.name doctor_name FROM appointments a JOIN users p ON p.id=a.patient_id JOIN users dr ON dr.id=a.doctor_id ORDER BY a.created_at DESC LIMIT 8'))})
                if path=='/api/admin/users':
                    self.auth(['admin']); return self.send_json(200,{'users':rows(d.execute('SELECT id,name,email,phone,role,specialty,active,created_at FROM users ORDER BY role,name'))})
                if path=='/api/admin/rooms':
                    self.auth(['admin']); return self.send_json(200,{'rooms':rows(d.execute("SELECT r.*,u.name doctor_name FROM rooms r LEFT JOIN users u ON u.id=r.doctor_id ORDER BY r.name")),'doctors':rows(d.execute("SELECT id,name,specialty FROM users WHERE role='doctor' AND active ORDER BY name"))})
                if path=='/api/admin/support/messages':
                    self.auth(['admin']); return self.send_json(200,{'messages':rows(d.execute('SELECT m.id,m.user_id,m.sender_role,m.message,m.created_at,u.name user_name,u.role user_role FROM support_messages m JOIN users u ON u.id=m.user_id ORDER BY m.created_at,m.id'))})
                if path=='/api/admin/catalog':
                    self.auth(['admin']); return self.send_json(200,{'catalog':rows(d.execute('SELECT * FROM catalog ORDER BY kind,name'))})
                if path=='/api/admin/observability':
                    self.auth(['admin']); return self.send_json(200,{'app':'healthy','requests':METRICS['requests'],'errors':METRICS['errors'],'avg_latency_ms':round(sum(METRICS['latencies'][-100:])/max(1,len(METRICS['latencies'][-100:])),1),'cpu_percent':None,'memory_percent':None,'runtime_metrics_status':'local_demo','note':'Bản chạy local hiện chưa thu thập CPU/RAM máy chủ. Các chỉ số này có trong cấu hình triển khai Docker qua Prometheus và node-exporter.'})
                return self.send_json(404,{'error':'Không tìm thấy đường dẫn.'})
        except PermissionError as e: METRICS['errors']+=1; self.send_json(403,{'error':str(e)})
        except ValueError as e: METRICS['errors']+=1; self.send_json(401,{'error':str(e)})
        except Exception as e:
            METRICS['errors']+=1
            print(f'[api] {method} {urlparse(self.path).path}: {type(e).__name__}: {e}',flush=True)
            self.send_json(500,{'error':'Lỗi máy chủ.','detail':str(e)})
        finally: METRICS['latencies'].append((time.time()-started)*1000)
    def do_api_post(self): pass
    def route_post(self,path,data,user,d): pass

def _dispatch_mutations():
    original=Handler.route
    def route(self,method):
        path=urlparse(self.path).path
        if path.startswith('/api/') and method in ('POST','PUT','DELETE') and path not in ('/api/auth/login','/api/auth/register'):
            started=time.time(); METRICS['requests']+=1
            try:
                data=self.body(); user=self.auth();
                with connect() as d:
                    if path=='/api/appointments' and method=='POST':
                        if user['role']!='patient': return self.send_json(403,{'error':'Chỉ bệnh nhân mới được đặt lịch.'})
                        doctor=d.execute("SELECT id FROM users WHERE id=? AND role='doctor' AND active",(data.get('doctor_id'),)).fetchone(); appointment_date=data.get('date',''); slot=data.get('slot','')
                        if not doctor or not appointment_date or not slot or not data.get('symptoms'): return self.send_json(400,{'error':'Vui lòng chọn bác sĩ, ngày, giờ và mô tả triệu chứng.'})
                        try: weekday=date.fromisoformat(appointment_date).weekday()
                        except Exception: return self.send_json(400,{'error':'Ngày khám không hợp lệ.'})
                        if not d.execute('SELECT id FROM availability WHERE doctor_id=? AND weekday=? AND slot=?',(data['doctor_id'],weekday,slot)).fetchone(): return self.send_json(409,{'error':'Bác sĩ không làm việc vào khung giờ đã chọn.'})
                        try: cur=d.execute('INSERT INTO appointments(patient_id,doctor_id,date,slot,symptoms) VALUES(?,?,?,?,?) RETURNING id',(user['id'],data['doctor_id'],appointment_date,slot,data['symptoms']))
                        except INTEGRITY_ERROR: return self.send_json(409,{'error':'Khung giờ này đã được đặt. Vui lòng chọn giờ khác.'})
                        return self.send_json(201,{'id':cur.fetchone()['id'],'status':'pending'})
                    if path=='/api/support/messages' and method=='POST':
                        message=data.get('message','').strip()
                        if not message or len(message)>2000: return self.send_json(400,{'error':'Tin nhắn không được để trống và tối đa 2000 ký tự.'})
                        cur=d.execute('INSERT INTO support_messages(user_id,sender_role,message) VALUES(?,?,?) RETURNING id',(user['id'],user['role'],message))
                        return self.send_json(201,{'id':cur.fetchone()['id']})
                    if path=='/api/admin/support/messages' and method=='POST':
                        self.auth(['admin']); message=data.get('message','').strip(); uid=data.get('user_id')
                        if not message or len(message)>2000: return self.send_json(400,{'error':'Tin nhắn không được để trống và tối đa 2000 ký tự.'})
                        if not d.execute('SELECT id FROM users WHERE id=?',(uid,)).fetchone(): return self.send_json(404,{'error':'Không tìm thấy người dùng.'})
                        cur=d.execute("INSERT INTO support_messages(user_id,sender_role,message) VALUES(?,'admin',?) RETURNING id",(uid,message))
                        return self.send_json(201,{'id':cur.fetchone()['id']})
                    if path.startswith('/api/appointments/') and path.endswith('/status') and method=='PUT':
                        self.auth(['doctor','admin']); aid=int(path.split('/')[-2]); status=data.get('status')
                        if status not in ('confirmed','cancelled'): return self.send_json(400,{'error':'Trạng thái không hợp lệ.'})
                        cur=d.execute("UPDATE appointments SET status=?,cancel_reason=? WHERE id=? AND (?='admin' OR doctor_id=?) AND status='pending'",(status,data.get('reason',''),aid,user['role'],user['id']))
                        if not cur.rowcount: return self.send_json(404,{'error':'Không tìm thấy lịch chờ duyệt.'})
                        return self.send_json(200,{'ok':True})
                    if path=='/api/records' and method=='POST':
                        self.auth(['doctor']); ap=d.execute("SELECT * FROM appointments WHERE id=? AND doctor_id=? AND status='confirmed'",(data.get('appointment_id'),user['id'])).fetchone()
                        if not ap: return self.send_json(400,{'error':'Chỉ có thể ghi hồ sơ cho lịch đã xác nhận của bạn.'})
                        cur=d.execute('INSERT INTO records(appointment_id,patient_id,doctor_id,diagnosis,symptoms,conclusion,prescription) VALUES(?,?,?,?,?,?,?) RETURNING id',(ap['id'],ap['patient_id'],user['id'],data.get('diagnosis',''),data.get('symptoms',''),data.get('conclusion',''),json.dumps(data.get('prescription',[]),ensure_ascii=False)))
                        d.execute("UPDATE appointments SET status='completed' WHERE id=?",(ap['id'],)); return self.send_json(201,{'id':cur.fetchone()['id']})
                    if path=='/api/profile' and method=='PUT':
                        if user['role']=='doctor': d.execute('UPDATE users SET name=?,phone=?,specialty=?,bio=?,fee=? WHERE id=?',(data.get('name',user['name']),data.get('phone',user.get('phone','')),data.get('specialty',user.get('specialty','')),data.get('bio',user.get('bio','')),int(data.get('fee',user.get('fee',0))),user['id']))
                        else: d.execute('UPDATE users SET name=?,phone=?,medical_history=? WHERE id=?',(data.get('name',user['name']),data.get('phone',user.get('phone','')),data.get('medical_history',user.get('medical_history','')),user['id']))
                        return self.send_json(200,{'ok':True})
                    if path=='/api/availability' and method=='PUT':
                        self.auth(['doctor']); d.execute('DELETE FROM availability WHERE doctor_id=?',(user['id'],))
                        for item in data.get('availability',[]):
                            day=int(item['weekday']); slot=item['slot']
                            if day not in range(7) or slot not in ('09:00','10:00','11:00','14:00','15:00','16:00'): return self.send_json(400,{'error':'Lịch làm việc không hợp lệ.'})
                            d.execute('INSERT INTO availability(doctor_id,weekday,slot) VALUES(?,?,?) ON CONFLICT(doctor_id,weekday,slot) DO NOTHING',(user['id'],day,slot))
                        return self.send_json(200,{'ok':True})
                    if path.startswith('/api/admin/users/') and path.endswith('/status') and method=='PUT':
                        self.auth(['admin']); uid=int(path.split('/')[-2]); d.execute("UPDATE users SET active=? WHERE id=? AND role<>'admin'",((bool(data.get('active')) if DATABASE_URL else (1 if data.get('active') else 0)),uid)); return self.send_json(200,{'ok':True})
                    if path=='/api/admin/users' and method=='POST':
                        self.auth(['admin']); password=data.get('password','')
                        if len(password)<8 or data.get('role') not in ('doctor','admin'): return self.send_json(400,{'error':'Tài khoản bác sĩ/quản trị cần mật khẩu ít nhất 8 ký tự.'})
                        try: cur=d.execute('INSERT INTO users(name,email,phone,role,specialty,bio,fee,password) VALUES(?,?,?,?,?,?,?,?) RETURNING id',(data.get('name'),data.get('email','').lower(),data.get('phone',''),data['role'],data.get('specialty',''),data.get('bio',''),int(data.get('fee',0)),pw_hash(password)))
                        except INTEGRITY_ERROR: return self.send_json(409,{'error':'Email đã tồn tại.'})
                        return self.send_json(201,{'id':cur.fetchone()['id']})
                    if path=='/api/admin/rooms' and method=='POST':
                        self.auth(['admin']); name=data.get('name','').strip(); capacity=int(data.get('capacity',1)); doctor_id=data.get('doctor_id') or None
                        if not name or capacity<1: return self.send_json(400,{'error':'Tên phòng và sức chứa hợp lệ là bắt buộc.'})
                        if doctor_id and not d.execute("SELECT id FROM users WHERE id=? AND role='doctor' AND active",(doctor_id,)).fetchone(): return self.send_json(400,{'error':'Bác sĩ phụ trách không hợp lệ.'})
                        try: cur=d.execute('INSERT INTO rooms(name,location,capacity,doctor_id) VALUES(?,?,?,?) RETURNING id',(name,data.get('location','').strip(),capacity,doctor_id))
                        except INTEGRITY_ERROR: return self.send_json(409,{'error':'Tên phòng đã tồn tại.'})
                        return self.send_json(201,{'id':cur.fetchone()['id']})
                    if path.startswith('/api/admin/rooms/') and method=='PUT':
                        self.auth(['admin']); rid=int(path.split('/')[-1]); name=data.get('name','').strip(); capacity=int(data.get('capacity',1)); doctor_id=data.get('doctor_id') or None
                        if not name or capacity<1: return self.send_json(400,{'error':'Tên phòng và sức chứa hợp lệ là bắt buộc.'})
                        if doctor_id and not d.execute("SELECT id FROM users WHERE id=? AND role='doctor' AND active",(doctor_id,)).fetchone(): return self.send_json(400,{'error':'Bác sĩ phụ trách không hợp lệ.'})
                        try: cur=d.execute('UPDATE rooms SET name=?,location=?,capacity=?,doctor_id=?,active=? WHERE id=?',(name,data.get('location','').strip(),capacity,doctor_id,(bool(data.get('active',True)) if DATABASE_URL else (1 if data.get('active',True) else 0)),rid))
                        except INTEGRITY_ERROR: return self.send_json(409,{'error':'Tên phòng đã tồn tại.'})
                        if not cur.rowcount: return self.send_json(404,{'error':'Không tìm thấy phòng.'})
                        return self.send_json(200,{'ok':True})
                    if path.startswith('/api/admin/rooms/') and method=='DELETE':
                        self.auth(['admin']); rid=int(path.split('/')[-1]); cur=d.execute('DELETE FROM rooms WHERE id=?',(rid,))
                        if not cur.rowcount: return self.send_json(404,{'error':'Không tìm thấy phòng.'})
                        return self.send_json(200,{'ok':True})
                    if path.startswith('/api/admin/appointments/') and path.endswith('/room') and method=='PUT':
                        self.auth(['admin']); aid=int(path.split('/')[-2]); rid=data.get('room_id') or None
                        if rid:
                            room=d.execute('SELECT * FROM rooms WHERE id=? AND active',(rid,)).fetchone()
                            ap=d.execute('SELECT date,slot,doctor_id FROM appointments WHERE id=?',(aid,)).fetchone()
                            if not room: return self.send_json(400,{'error':'Phòng không tồn tại hoặc đã ngừng hoạt động.'})
                            if not ap: return self.send_json(404,{'error':'Không tìm thấy lịch hẹn.'})
                            if room['doctor_id'] and room['doctor_id']!=ap['doctor_id']: return self.send_json(409,{'error':'Phòng này đang được gắn với bác sĩ khác.'})
                            occupied=d.execute("SELECT count(*) count FROM appointments WHERE room_id=? AND date=? AND slot=? AND status IN ('pending','confirmed') AND id<>?",(rid,ap['date'],ap['slot'],aid)).fetchone()['count']
                            if occupied>=room['capacity']: return self.send_json(409,{'error':'Phòng đã đủ sức chứa trong khung giờ này.'})
                        cur=d.execute('UPDATE appointments SET room_id=? WHERE id=?',(rid,aid))
                        if not cur.rowcount: return self.send_json(404,{'error':'Không tìm thấy lịch hẹn.'})
                        return self.send_json(200,{'ok':True})
                    if path=='/api/admin/catalog' and method=='POST':
                        self.auth(['admin']);
                        try: cur=d.execute('INSERT INTO catalog(kind,name,description) VALUES(?,?,?) RETURNING id',(data['kind'],data['name'],data.get('description','')))
                        except (INTEGRITY_ERROR,KeyError): return self.send_json(409,{'error':'Danh mục không hợp lệ hoặc tên đã tồn tại.'})
                        return self.send_json(201,{'id':cur.fetchone()['id']})
                    if path.startswith('/api/admin/catalog/') and method=='DELETE':
                        self.auth(['admin']); d.execute('DELETE FROM catalog WHERE id=?',(int(path.split('/')[-1]),)); return self.send_json(200,{'ok':True})
                self.send_json(404,{'error':'Không tìm thấy đường dẫn.'})
            except PermissionError as e: METRICS['errors']+=1; self.send_json(403,{'error':str(e)})
            except ValueError as e: METRICS['errors']+=1; self.send_json(401,{'error':str(e)})
            except Exception as e:
                METRICS['errors']+=1
                print(f'[api] {method} {path}: {type(e).__name__}: {e}',flush=True)
                self.send_json(500,{'error':'Lỗi máy chủ.','detail':str(e)})
            finally: METRICS['latencies'].append((time.time()-started)*1000)
        else: return original(self,method)
    Handler.route=route

if __name__=='__main__':
    init_db(); _dispatch_mutations(); port=int(os.environ.get('PORT','8000'))
    print(f'An Tam API and web app at http://localhost:{port}')
    ThreadingHTTPServer(('0.0.0.0',port),Handler).serve_forever()
