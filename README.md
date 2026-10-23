# ShopManager desktop MVP
Python 3.11+; tested structure for macOS and Windows.

Setup:
```bash
python -m venv .venv
source .venv/bin/activate # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```
On first run create the owner account in the setup window. No default password. Data is stored in `shopmanager.db` next to the app. Back it up regularly.

Features: login, owner/manager/cashier roles, searchable inventory, archive, purchases with weighted average cost, atomic sales with stock deduction, low-stock dashboard, sales reports, CSV export, PDF invoice, supplier reorder CSV.

Important limitations: this is a runnable MVP, not a completed commissioned product. It is a **single-machine SQLite** deployment. Do not put the SQLite file on a shared network drive; multi-terminal deployment needs a database server and concurrency testing. PDF print via system PDF viewer. No Windows installer, production security audit, automated test suite, or validated acceptance tests yet. Do not promise client delivery without these.
