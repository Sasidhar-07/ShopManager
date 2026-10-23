import sys,csv
from pathlib import Path
from PySide6.QtWidgets import (QApplication,QWidget,QMainWindow,QVBoxLayout,QHBoxLayout,QFormLayout,QLineEdit,QPushButton,QLabel,QTabWidget,QTableWidget,QTableWidgetItem,QSpinBox,QDoubleSpinBox,QComboBox,QMessageBox,QInputDialog,QFileDialog,QHeaderView)
import database as d
from reportlab.platypus import SimpleDocTemplate,Paragraph,Table,Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

def money(n):return f'{n/100:,.2f}'
def cell(v):return QTableWidgetItem(str(v))
def table(headers,rows):
 t=QTableWidget();t.setColumnCount(len(headers));t.setHorizontalHeaderLabels(headers);t.setRowCount(len(rows));t.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows);t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
 for i,row in enumerate(rows):
  for j,value in enumerate(row):t.setItem(i,j,cell(value))
 t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
 return t
class App(QMainWindow):
 def __init__(self):
  super().__init__();self.user=None;self.cart=[];self.setWindowTitle('ShopManager');self.resize(1080,730);self.auth()
 def error(self,e):QMessageBox.warning(self,'ShopManager',str(e))
 def auth(self):
  w=QWidget();l=QVBoxLayout(w);l.addStretch();title=QLabel('ShopManager — '+('Create Owner' if d.first_run() else 'Sign in'));title.setStyleSheet('font-size:26px;font-weight:bold');l.addWidget(title)
  self.email=QLineEdit();self.email.setPlaceholderText('Email');l.addWidget(self.email)
  self.password=QLineEdit();self.password.setPlaceholderText('Password (10+ characters for setup)');self.password.setEchoMode(QLineEdit.EchoMode.Password);l.addWidget(self.password)
  b=QPushButton('Create Owner' if d.first_run() else 'Login');b.clicked.connect(self.do_login);l.addWidget(b);l.addStretch();self.setCentralWidget(w)
 def do_login(self):
  try:
   if d.first_run():d.create_owner(self.email.text(),self.password.text())
   self.user=d.login(self.email.text(),self.password.text())
   if not self.user:raise ValueError('Invalid credentials')
   self.home()
  except Exception as e:self.error(e)
 def home(self):
  self.tabs=QTabWidget();self.setCentralWidget(self.tabs)
  for name,fn in [('Dashboard',self.dashboard),('Inventory',self.inventory),('Sales',self.sales),('Purchases',self.purchases),('Reports',self.reports)]:
   if name=='Purchases' and self.user['role']=='cashier':continue
   if name=='Reports' and self.user['role']=='cashier':continue
   w=QWidget();self.tabs.addTab(w,name);fn(w)
  if self.user['role']=='owner':
   w=QWidget();self.tabs.addTab(w,'Users');self.user_tab(w)
  self.tabs.currentChanged.connect(lambda _:self.refresh())
 def refresh(self):
  if hasattr(self,'tabs'):
   index=self.tabs.currentIndex();name=self.tabs.tabText(index)
   w=self.tabs.widget(index)
   {'Dashboard':self.dashboard,'Inventory':self.inventory,'Sales':self.sales,'Purchases':self.purchases,'Reports':self.reports,'Users':self.user_tab}[name](w)
 def layout(self,w):
  if w.layout():
   old=w.layout()
   while old.count():
    item=old.takeAt(0)
    if item.widget():item.widget().deleteLater()
  else:old=QVBoxLayout(w)
  return old
 def dashboard(self,w):
  l=self.layout(w);s=d.stats();l.addWidget(QLabel(f"Active products: {s['products']}     Low stock: {s['low']}     Stock value at cost: {money(s['stock'])}"))
  rows=[(p['sku'],p['name'],p['supplier'],p['qty'],p['reorder']) for p in d.products() if p['qty']<=p['reorder']]
  l.addWidget(QLabel('Needs restocking'));l.addWidget(table(['SKU','Name','Supplier','Qty','Reorder at'],rows))
  b=QPushButton('Export supplier reorder CSV');b.clicked.connect(self.reorder_export);l.addWidget(b)
 def inventory(self,w):
  l=self.layout(w);search=QLineEdit();search.setPlaceholderText('Search SKU, name or supplier');l.addWidget(search)
  t=table(['ID','SKU','Name','Supplier','Sale price','Avg cost','Qty','Reorder'],[]);l.addWidget(t)
  def fill():
   rows=[(p['id'],p['sku'],p['name'],p['supplier'],money(p['price_cents']),money(p['cost_cents']),p['qty'],p['reorder']) for p in d.products(search.text())]
   t.setRowCount(len(rows))
   for i,row in enumerate(rows):
    for j,v in enumerate(row):t.setItem(i,j,cell(v))
  search.textChanged.connect(lambda _:fill());fill()
  if self.user['role']!='cashier':
   bar=QHBoxLayout();add=QPushButton('Add product');add.clicked.connect(self.add_product);bar.addWidget(add)
   arch=QPushButton('Archive selected');arch.clicked.connect(lambda:self.archive_selected(t));bar.addWidget(arch);l.addLayout(bar)
 def ask(self,title,label,default=''):
  v,ok=QInputDialog.getText(self,title,label,text=default)
  if not ok:raise InterruptedError()
  return v.strip()
 def integer(self,title,label,minimum=0):
  v,ok=QInputDialog.getInt(self,title,label,minimum,minimum,10000000)
  if not ok:raise InterruptedError()
  return v
 def amount(self,title,label):
  v,ok=QInputDialog.getDouble(self,title,label,0,0,100000000,2)
  if not ok:raise InterruptedError()
  return round(v*100)
 def add_product(self):
  try:
   sku=self.ask('New product','SKU');name=self.ask('New product','Name');supplier=self.ask('New product','Supplier');price=self.amount('New product','Sale price');cost=self.amount('New product','Purchase cost');qty=self.integer('New product','Initial stock');reorder=self.integer('New product','Reorder threshold',5)
   d.add_product(sku,name,supplier,price,cost,qty,reorder);self.refresh()
  except InterruptedError:pass
  except Exception as e:self.error(e)
 def selected_id(self,t):
  row=t.currentRow()
  if row<0:raise ValueError('Select a row first')
  return int(t.item(row,0).text())
 def archive_selected(self,t):
  try:
   pid=self.selected_id(t)
   if QMessageBox.question(self,'Confirm','Archive this product?')==QMessageBox.StandardButton.Yes:d.archive(pid);self.refresh()
  except Exception as e:self.error(e)
 def purchases(self,w):
  l=self.layout(w);ps=d.products();self.purchase_select=QComboBox()
  for p in ps:self.purchase_select.addItem(f"{p['sku']} — {p['name']}",p['id'])
  l.addWidget(QLabel('Receive stock'));l.addWidget(self.purchase_select)
  self.purchase_qty=QSpinBox();self.purchase_qty.setRange(1,100000);l.addWidget(QLabel('Quantity'));l.addWidget(self.purchase_qty)
  self.purchase_cost=QDoubleSpinBox();self.purchase_cost.setRange(0,10000000);self.purchase_cost.setDecimals(2);l.addWidget(QLabel('Unit cost'));l.addWidget(self.purchase_cost)
  b=QPushButton('Record purchase');b.clicked.connect(self.save_purchase);l.addWidget(b);l.addStretch()
 def save_purchase(self):
  try:d.purchase(self.user['id'],self.purchase_select.currentData(),self.purchase_qty.value(),round(self.purchase_cost.value()*100));self.refresh();QMessageBox.information(self,'Saved','Purchase recorded')
  except Exception as e:self.error(e)
 def sales(self,w):
  l=self.layout(w);self.sale_select=QComboBox()
  for p in d.products():self.sale_select.addItem(f"{p['sku']} — {p['name']} (stock {p['qty']})",p['id'])
  l.addWidget(self.sale_select);self.sale_qty=QSpinBox();self.sale_qty.setRange(1,100000);l.addWidget(self.sale_qty)
  add=QPushButton('Add to cart');add.clicked.connect(self.add_cart);l.addWidget(add)
  self.cart_table=table(['Product ID','Quantity'],self.cart);l.addWidget(self.cart_table)
  clear=QPushButton('Clear cart');clear.clicked.connect(lambda:(self.cart.clear(),self.refresh()));l.addWidget(clear)
  checkout=QPushButton('Complete sale (atomic transaction)');checkout.clicked.connect(self.checkout);l.addWidget(checkout)
 def add_cart(self):
  if self.sale_select.currentData() is not None:self.cart.append((self.sale_select.currentData(),self.sale_qty.value()));self.refresh()
 def checkout(self):
  try:
   sid=d.sale(self.user['id'],self.cart);self.cart=[];self.refresh();QMessageBox.information(self,'Sale saved',f'Sale #{sid} saved. Create PDF invoice from Reports.')
  except Exception as e:self.error(e)
 def reports(self,w):
  l=self.layout(w);rows=d.report();l.addWidget(QLabel('Revenue: '+money(sum(x['total_cents'] for x in rows))+'     Gross profit: '+money(sum(x['profit_cents'] for x in rows))))
  t=table(['ID','Date','Cashier','Revenue','Gross profit'],[(r['id'],r['created_at'],r['cashier'],money(r['total_cents']),money(r['profit_cents'])) for r in rows]);l.addWidget(t)
  b=QPushButton('Export sales CSV');b.clicked.connect(lambda:self.csv_export('sales.csv',['ID','Date','Cashier','Revenue cents','Profit cents'],[(r['id'],r['created_at'],r['cashier'],r['total_cents'],r['profit_cents']) for r in rows]));l.addWidget(b)
  pdf=QPushButton('Save selected invoice as PDF');pdf.clicked.connect(lambda:self.pdf_invoice(self.selected_id(t)));l.addWidget(pdf)
 def user_tab(self,w):
  l=self.layout(w);l.addWidget(table(['ID','Email','Role','Active'],[(u['id'],u['email'],u['role'],u['active']) for u in d.users()]));b=QPushButton('Create staff account');b.clicked.connect(self.new_user);l.addWidget(b)
 def new_user(self):
  try:
   email=self.ask('Staff','Email');pw=self.ask('Staff','Temporary password (10+ characters)');role,ok=QInputDialog.getItem(self,'Staff','Role',['manager','cashier'],0,False)
   if not ok:return
   d.add_user(email,pw,role);self.refresh()
  except InterruptedError:pass
  except Exception as e:self.error(e)
 def csv_export(self,name,headers,rows):
  path,_=QFileDialog.getSaveFileName(self,'Save CSV',name,'CSV files (*.csv)')
  if not path:return
  with open(path,'w',newline='',encoding='utf-8-sig') as f:
   writer=csv.writer(f);writer.writerow(headers)
   for row in rows:writer.writerow(["'"+v if isinstance(v,str) and v.lstrip().startswith(('=','+','-','@','\t','\r')) else v for v in row])
  QMessageBox.information(self,'Exported','CSV saved')
 def reorder_export(self):
  self.csv_export('reorder.csv',['SKU','Name','Supplier','Qty','Reorder threshold'],[(p['sku'],p['name'],p['supplier'],p['qty'],p['reorder']) for p in d.products() if p['qty']<=p['reorder']])
 def pdf_invoice(self,sid):
  sale,lines=d.invoice(sid)
  if not sale:return
  path,_=QFileDialog.getSaveFileName(self,'Save PDF',f'invoice_{sid}.pdf','PDF files (*.pdf)')
  if not path:return
  styles=getSampleStyleSheet();story=[Paragraph('ShopManager - Invoice #'+str(sid),styles['Title']),Paragraph('Date: '+sale['created_at'],styles['Normal']),Spacer(1,16)]
  rows=[['Item','Qty','Price','Subtotal']]+[[x['name'],str(x['qty']),money(x['price_cents']),money(x['qty']*x['price_cents'])] for x in lines]+[['TOTAL','','',money(sale['total_cents'])]]
  t=Table(rows,repeatRows=1);t.setStyle([('GRID',(0,0),(-1,-1),0.5,colors.grey),('BACKGROUND',(0,0),(-1,0),colors.lightgrey)]);story.append(t);SimpleDocTemplate(path).build(story);QMessageBox.information(self,'Saved','Invoice PDF created')
if __name__=='__main__':
 d.init();app=QApplication(sys.argv);app.setStyle('Fusion');win=App();win.show();sys.exit(app.exec())
