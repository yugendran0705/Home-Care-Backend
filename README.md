# Home-Care Backend

It is built using Python with the [FastAPI](https://fastapi.tiangolo.com/) framework, [SQLAlchemy](https://www.sqlalchemy.org/) for ORM, and [Alembic](https://alembic.sqlalchemy.org/) for database migrations.

## Prerequisites

Before you begin, ensure you have the following installed:
- [Python 3.10+](https://www.python.org/)
- [PostgreSQL](https://www.postgresql.org/)
- A virtual environment tool (`venv`)

## Getting Started

Follow these steps to get your development environment set up.

### 1. Clone the Repository

```bash
git clone <your-repository-url>
cd home-care-backend
```

### 2. Create and Activate Virtual Environment

It's highly recommended to use a virtual environment to manage project dependencies.

```bash
# Create a virtual environment
python3 -m venv .venv

# Activate the virtual environment
# On macOS and Linux:
source .venv/bin/activate
# On Windows:
# .\.venv\Scripts\activate
```

### 3. Install Dependencies

Install all the required packages from `requirements.txt`.

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

The application uses a `.env` file for environment variables. Create one by copying the example file (you may need to create `.env.example` first).

```bash
cp .env.example .env
```

Now, open the `.env` file and update the variables with your local configuration, especially the `DATABASE_URL`.

### 5. Database Migrations

This project uses Alembic to manage database schema changes.

- **To generate a new migration script** after changing your SQLAlchemy models:
  ```bash
  alembic revision --autogenerate -m "A descriptive message about the changes"
  ```

- **To apply the latest migrations** to your database:
  ```bash
  alembic upgrade head
  ```

## Running the Application

To start the development server, run the following command from the root directory (assuming your main FastAPI app instance is in `main.py`):

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The server will start on `http://127.0.0.1:8000`. The `--reload` flag enables hot-reloading, so the server will restart automatically on code changes.

## API Documentation

FastAPI provides automatic interactive API documentation. Once the server is running, you can access it at:

- **Swagger UI**: http://127.0.0.1:8000/docs
- **ReDoc**: http://127.0.0.1:8000/redoc

## Contributing

When working on a ticket, please follow this branching strategy.

### Branching Strategy

Create a new branch from `main` for each ticket. The branch name should be in the following format:

`{Type of ticket}/{Ticket number}-{Small_description_with_underscores}`

**Types of tickets:**

- `feature`: For new features.
- `bugfix`: For bug fixes.
- `chore`: for routine tasks, maintenance, or refactoring.
- and more as needed.

**Example:**

`feature/123-add_new_profile_screen`
`bugfix/456-fix_login_issue`
`chore/789-update_dependencies`

### Commit Messages

Please use the following format for your commit messages:

`{Type of ticket}: {Ticket number}-{what you have solved}`

**Example:**

`feature: 123 Implemented the new profile screen UI`

- https://api.postman.com/collections/26433342-4b48923a-e40b-41dd-a649-aa3fb3e77e2b?access_key=PMAT-01KGJ6P9BMGZW0NBMNB61DES39


## Indexes created
✅ Indexes by Table:
| Table           | Indexes | Key Indexes Added                                                              |
| --------------- | ------- | ------------------------------------------------------------------------------ |
| bookings        | 12      | patient_id, nurse_id, service_id, booking_status, scheduled times, composites |
| availability    | 6       | nurse_id, is_booked, start_time, end_time, composites                         |
| users           | 5       | user_type, is_active, email, created_at, last_login                           |
| nurses          | 5       | address_id, is_verified, is_qualified, is_active, verified_active             |
| payments        | 4       | patient_id, payment_status, payment_date, patient_status                      |
| reviews         | 3       | patient_id, nurse_id, review_date                                             |
| addresses       | 2       | user_id, city_state                                                           |
| services        | 2       | is_active, is_qualified                                                       |
| nurse_services  | 2       | nurse_id, service_id                                                          |
| nurse_documents | 2       | nurse_id, verification_status                                                 |
| patients        | 1       | address_id                                                                    |
| patients        | 1       | address_id                                                       |
