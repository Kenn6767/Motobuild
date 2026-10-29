# MotoBuild — Motorcycle Parts Compatibility & Ordering

A Flask + SQLAlchemy database project for CIS 104. Customers filter demo parts by motorcycle, place orders, and track approval. Admins approve/reject orders and manage parts. It is designed for GitHub, Render, and PostgreSQL-compatible providers such as Aiven.

## Features
- Six normalized relational tables: `users`, `motorcycles`, `parts`, `part_compatibility`, `orders`, `order_items`.
- Compatibility search using a many-to-many junction table.
- Customer registration/login, order placement, order history.
- Admin order approval/rejection and parts CRUD (create, read, update, delete/archive).
- Stock checks and transactional order creation; PostgreSQL row lock helps reduce overselling.
- Three meaningful query examples including two JOIN queries in `docs/DATABASE_DESIGN.md`.
- Health endpoint: `/health`.

## Run locally
Requires Python 3.10+.

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```
Open http://127.0.0.1:5000.

Local default is SQLite (`motobuild.db`). To use PostgreSQL locally, set `DATABASE_URL` and `SECRET_KEY` environment variables first. Copy `.env.example` as a reference; Flask does not automatically load `.env`, so set variables in your terminal or hosting dashboard.

## Demo accounts
- Admin: `admin@motobuild.demo` / `AdminDemo123!`
- Customer: `rider@example.com` / `RiderDemo123!`

**Change the demo admin password before public deployment.** Seed accounts are created only when the database is empty. For a hosted database, set `DEMO_ADMIN_PASSWORD` before the first boot. Never publish a production database URL or secret.

## Deploy to Render + Aiven
1. Push this folder to a GitHub repository.
2. Create a PostgreSQL database in Aiven. Copy its PostgreSQL connection URI and ensure SSL is enabled (`sslmode=require`).
3. In Render, create a Web Service from the GitHub repository. Render can use `render.yaml`; set `DATABASE_URL` in the service environment to the Aiven URI, and set `SECRET_KEY` to a long random value.
4. Keep the URL in the provider's environment settings only; never commit it into GitHub.
5. Deploy. Visit `/health`; expected response is `{"status":"ok","database":"connected"}`.
6. First boot creates tables and demo records. If deploying with a pre-existing database, back it up first and check for table-name conflicts.

Aiven/Render connection URLs sometimes begin with `postgres://`; the app normalizes this to `postgresql://`. The PostgreSQL driver is included in `requirements.txt`.

## Important project notes
- Product image URLs are external PNG URLs and require internet access in the browser. They are sample visuals, not proof of exact motorcycle fitment. Confirm part compatibility with the manufacturer or a qualified mechanic before real purchases.
- This is an academic demo, not a production commerce system. Add CSRF protection, rate limiting, email verification, payment integration, inventory audit logs, and stronger order state rules before real commercial use.
- The demo order form does not collect payment information.
- If changing database schemas after deployment, use a migration tool such as Flask-Migrate/Alembic rather than relying on `create_all()`.

## Documentation
See `docs/DATABASE_DESIGN.md` for system overview, business rules, UNF-to-3NF discussion, ER diagram, queries, transaction/concurrency scenarios, and defense flow.
