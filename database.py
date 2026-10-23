import sqlite3, hashlib, secrets, hmac
from pathlib import Path
from contextlib import contextmanager
DB=Path(__file__).resolve().parent/'shopmanager.db'
def hash_password(p):
 salt=secrets.token_bytes(16)
 return salt.hex()+':'+hashlib.pbkdf2_hmac('sha256',p.encode(),salt,600000).hex()
def check_password(p,h):
 try:
  s,d=h.split(':'); v=hashlib.pbkdf2_hmac('sha256',p.encode(),bytes.fromhex(s),600000)
  return hmac.compare_digest(v,bytes.fromhex(d))
 except (ValueError,TypeError): return False
@contextmanager
def db():
 c=sqlite3.connect(DB,timeout=15)
 c.row_factory=sqlite3.Row
 c.execute('PRAGMA foreign_keys=ON');c.execute('PRAGMA busy_timeout=15000')
 try:
  yield c;c.commit()
 except Exception:
  c.rollback();raise
 finally:c.close()
def init():
 with db() as c:
  c.execute('PRAGMA journal_mode=WAL')
  c.executescript("""CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,email TEXT UNIQUE NOT NULL,password TEXT NOT NULL,role TEXT NOT NULL CHECK(role IN ('owner','manager','cashier')),active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY,sku TEXT UNIQUE NOT NULL,name TEXT NOT NULL,supplier TEXT NOT NULL DEFAULT '',price_cents INTEGER NOT NULL CHECK(price_cents>=0),cost_cents INTEGER NOT NULL DEFAULT 0 CHECK(cost_cents>=0),qty INTEGER NOT NULL DEFAULT 0 CHECK(qty>=0),reorder INTEGER NOT NULL DEFAULT 5 CHECK(reorder>=0),archived INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS sales(id INTEGER PRIMARY KEY,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,cashier_id INTEGER NOT NULL REFERENCES users(id),total_cents INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS sale_lines(id INTEGER PRIMARY KEY,sale_id INTEGER NOT NULL REFERENCES sales(id),product_id INTEGER NOT NULL REFERENCES products(id),name TEXT NOT NULL,qty INTEGER NOT NULL,price_cents INTEGER NOT NULL,cost_cents INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS purchases(id INTEGER PRIMARY KEY,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,user_id INTEGER NOT NULL REFERENCES users(id),product_id INTEGER NOT NULL REFERENCES products(id),qty INTEGER NOT NULL,cost_cents INTEGER NOT NULL);""")
def first_run():
 with db() as c:return c.execute('SELECT COUNT(*) FROM users').fetchone()[0]==0
def create_owner(email,pw):
 if len(pw)<10:raise ValueError('Use a password of at least 10 characters')
 with db() as c:
  if c.execute('SELECT COUNT(*) FROM users').fetchone()[0]:raise ValueError('Owner already exists')
  c.execute('INSERT INTO users(email,password,role) VALUES(?,?,?)',(email.strip().lower(),hash_password(pw),'owner'))
def login(email,pw):
 with db() as c:
  r=c.execute('SELECT * FROM users WHERE email=? AND active=1',(email.strip().lower(),)).fetchone()
  return dict(r) if r and check_password(pw,r['password']) else None
def users():
 with db() as c:return [dict(x) for x in c.execute('SELECT id,email,role,active FROM users ORDER BY id')]
def add_user(email,pw,role):
 if role not in ('owner','manager','cashier') or len(pw)<10:raise ValueError('Invalid role or password too short')
 with db() as c:c.execute('INSERT INTO users(email,password,role) VALUES(?,?,?)',(email.strip().lower(),hash_password(pw),role))
def products(search='',include_archived=False):
 with db() as c:
  q='SELECT * FROM products WHERE (sku LIKE ? OR name LIKE ? OR supplier LIKE ?)'
  if not include_archived:q+=' AND archived=0'
  return [dict(r) for r in c.execute(q+' ORDER BY name',('%'+search+'%',)*3)]
def add_product(sku,name,supplier,price,cost,qty,reorder):
 if not sku.strip() or not name.strip() or min(price,cost,qty,reorder)<0:raise ValueError('Invalid product fields')
 with db() as c:c.execute('INSERT INTO products(sku,name,supplier,price_cents,cost_cents,qty,reorder) VALUES(?,?,?,?,?,?,?)',(sku.strip(),name.strip(),supplier.strip(),price,cost,qty,reorder))
def archive(pid):
 with db() as c:c.execute('UPDATE products SET archived=1 WHERE id=?',(pid,))
def purchase(uid,pid,qty,cost):
 if qty<=0 or cost<0:raise ValueError('Invalid purchase')
 with db() as c:
  c.execute('BEGIN IMMEDIATE')
  r=c.execute('SELECT qty,cost_cents,archived FROM products WHERE id=?',(pid,)).fetchone()
  if not r or r['archived']:raise ValueError('Product not available')
  newcost=(r['qty']*r['cost_cents']+qty*cost)//(r['qty']+qty)
  c.execute('UPDATE products SET qty=qty+?,cost_cents=? WHERE id=?',(qty,newcost,pid))
  c.execute('INSERT INTO purchases(user_id,product_id,qty,cost_cents) VALUES(?,?,?,?)',(uid,pid,qty,cost))
def sale(uid,items):
 if not items:raise ValueError('Cart empty')
 merged={}
 for pid,qty in items:
  if qty<=0:raise ValueError('Quantity must be positive')
  merged[pid]=merged.get(pid,0)+qty
 with db() as c:
  c.execute('BEGIN IMMEDIATE')
  lines=[]
  for pid,qty in merged.items():
   r=c.execute('SELECT * FROM products WHERE id=? AND archived=0',(pid,)).fetchone()
   if not r or r['qty']<qty:raise ValueError('Insufficient stock for product '+str(pid))
   lines.append((pid,r['name'],qty,r['price_cents'],r['cost_cents']))
  total=sum(q*p for _,_,q,p,_ in lines)
  sid=c.execute('INSERT INTO sales(cashier_id,total_cents) VALUES(?,?)',(uid,total)).lastrowid
  for pid,name,qty,price,cost in lines:
   c.execute('UPDATE products SET qty=qty-? WHERE id=?',(qty,pid))
   c.execute('INSERT INTO sale_lines(sale_id,product_id,name,qty,price_cents,cost_cents) VALUES(?,?,?,?,?,?)',(sid,pid,name,qty,price,cost))
  return sid
def invoice(sid):
 with db() as c:
  s=c.execute('SELECT s.*,u.email cashier FROM sales s JOIN users u ON u.id=s.cashier_id WHERE s.id=?',(sid,)).fetchone()
  ls=c.execute('SELECT * FROM sale_lines WHERE sale_id=?',(sid,)).fetchall()
  return (dict(s),[dict(r) for r in ls]) if s else (None,[])
def stats():
 with db() as c:
  return dict(c.execute('SELECT COUNT(*) products,COALESCE(SUM(CASE WHEN qty<=reorder THEN 1 ELSE 0 END),0) low,COALESCE(SUM(qty*cost_cents),0) stock FROM products WHERE archived=0').fetchone())
def report():
 with db() as c:
  return [dict(r) for r in c.execute("""SELECT s.id,s.created_at,u.email cashier,s.total_cents,COALESCE(SUM(l.qty*(l.price_cents-l.cost_cents)),0) profit_cents FROM sales s JOIN users u ON u.id=s.cashier_id JOIN sale_lines l ON l.sale_id=s.id GROUP BY s.id ORDER BY s.id DESC""")]
