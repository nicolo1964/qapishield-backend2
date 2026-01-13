# QAPIShield Backend API

Production-ready FastAPI backend for QAPIShield - QAPI and Compliance Management System for Skilled Nursing Facilities.

## Features

- **FastAPI Framework**: Modern, fast, async Python web framework
- **PostgreSQL Database**: Production-grade relational database with SQLAlchemy ORM
- **JWT Authentication**: Secure token-based authentication
- **Role-Based Access Control**: Admin, DON, MDS, and Nurse roles
- **Multi-Tenant Architecture**: Facility-level data isolation
- **PHI-Free Design**: No resident names, DOBs, or SSNs stored
- **Risk Assessment Engine**: Falls, pressure ulcers, infection, and readmission risk scoring
- **AI Care Plan Generator**: Automated care plan generation based on risk assessments
- **QAPI Dashboard**: Facility-wide analytics and high-risk summaries

## Tech Stack

- Python 3.11+
- FastAPI 0.109+
- PostgreSQL 14+
- SQLAlchemy 2.0+
- Pydantic 2.5+
- JWT (python-jose)
- Bcrypt password hashing

## Project Structure

```
qapishield-backend/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── auth.py          # Authentication endpoints
│   │       ├── facilities.py    # Facility management
│   │       ├── residents.py     # Resident management
│   │       ├── assessments.py   # Risk assessments
│   │       └── qapi.py          # QAPI dashboard
│   ├── core/
│   │   ├── config.py            # Configuration
│   │   ├── database.py          # Database connection
│   │   └── security.py          # JWT and password utilities
│   ├── models/
│   │   └── models.py            # SQLAlchemy models
│   ├── schemas/
│   │   └── schemas.py           # Pydantic schemas
│   ├── services/
│   │   └── risk_assessment.py  # Risk scoring and care plans
│   └── main.py                  # FastAPI application
├── alembic/                     # Database migrations
├── requirements.txt             # Python dependencies
├── .env.example                 # Environment variables template
└── README.md                    # This file
```

## Local Setup

### Prerequisites

- Python 3.11 or higher
- PostgreSQL 14 or higher
- pip or pipenv

### Installation Steps

1. **Clone or extract the backend code**

```bash
cd qapishield-backend
```

2. **Create virtual environment**

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**

```bash
pip install -r requirements.txt
```

4. **Set up PostgreSQL database**

```bash
# Create database
createdb qapishield

# Or using psql:
psql -U postgres
CREATE DATABASE qapishield;
\q
```

5. **Configure environment variables**

```bash
cp .env.example .env
# Edit .env with your actual values
```

Generate a secure SECRET_KEY:
```bash
openssl rand -hex 32
```

6. **Initialize database**

```bash
# Create tables
alembic upgrade head
```

7. **Run the development server**

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:
- API: http://localhost:8000
- Interactive docs: http://localhost:8000/api/docs
- Alternative docs: http://localhost:8000/api/redoc

## Render Deployment

### Prerequisites

- Render account (https://render.com)
- PostgreSQL database on Render

### Deployment Steps

1. **Create PostgreSQL Database on Render**

   - Go to Render Dashboard → New → PostgreSQL
   - Name: `qapishield-db`
   - Plan: Select appropriate plan
   - Copy the **Internal Database URL** after creation

2. **Create Web Service on Render**

   - Go to Render Dashboard → New → Web Service
   - Connect your Git repository or upload code
   - Configure:
     - **Name**: `qapishield-api`
     - **Environment**: Python 3
     - **Build Command**: `pip install -r requirements.txt`
     - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

3. **Set Environment Variables**

   In Render Web Service → Environment:
   
   ```
   DATABASE_URL=<your-render-postgres-internal-url>
   SECRET_KEY=<generate-with-openssl-rand-hex-32>
   ALGORITHM=HS256
   ACCESS_TOKEN_EXPIRE_MINUTES=30
   APP_NAME=QAPIShield
   DEBUG=False
   ALLOWED_ORIGINS=["https://your-frontend-domain.com"]
   ```

4. **Initialize Database**

   After first deployment, run migrations:
   
   - Go to Render Dashboard → Your Web Service → Shell
   - Run: `alembic upgrade head`

5. **Deploy**

   - Render will automatically deploy on git push
   - Or click "Manual Deploy" in Render Dashboard

Your API will be available at: `https://qapishield-api.onrender.com`

## API Endpoints

### Authentication

- `POST /api/v1/auth/register` - Register new facility with admin user
- `POST /api/v1/auth/login` - Login and get JWT token
- `GET /api/v1/auth/me` - Get current user info

### Facilities

- `GET /api/v1/facilities/me` - Get current user's facility
- `GET /api/v1/facilities/{facility_id}` - Get facility by ID

### Residents

- `POST /api/v1/residents/` - Add new resident (de-identified)
- `GET /api/v1/residents/` - List all residents in facility
- `GET /api/v1/residents/{resident_id}` - Get resident by ID
- `PATCH /api/v1/residents/{resident_id}/deactivate` - Deactivate resident

### Assessments

- `POST /api/v1/assessments/` - Create risk assessment
- `POST /api/v1/assessments/care-plan` - Generate AI care plan
- `GET /api/v1/assessments/resident/{resident_id}` - Get resident assessments
- `GET /api/v1/assessments/{assessment_id}` - Get assessment by ID

### QAPI Dashboard

- `GET /api/v1/qapi/dashboard` - Get facility dashboard with risk summaries
- `GET /api/v1/qapi/high-risk-residents` - Get list of high-risk residents

## Risk Assessment Types

The system supports four assessment types:

1. **Falls** (`falls`)
   - Risk factors: history of falls, mobility impairment, psychotropic medications, cognitive impairment, age, environmental factors
   - Scoring: 0-100 (High: ≥60, Moderate: 30-59, Low: <30)

2. **Pressure Ulcers** (`pressure_ulcers`)
   - Risk factors: immobility, poor nutrition, incontinence, existing pressure injuries, diabetes
   - Scoring: 0-100 (High: ≥60, Moderate: 30-59, Low: <30)

3. **Infection/Sepsis** (`infection`)
   - Risk factors: immunocompromised, recent hospitalization, indwelling devices, open wounds, respiratory conditions
   - Scoring: 0-100 (High: ≥60, Moderate: 30-59, Low: <30)

4. **Hospital Readmission** (`readmission`)
   - Risk factors: days since discharge, comorbidities, medication complexity, adherence history, social support
   - Scoring: 0-100 (High: ≥60, Moderate: 30-59, Low: <30)

## Security & Compliance

- **No PHI Storage**: Only de-identified Reference IDs are stored
- **JWT Authentication**: All endpoints (except register/login) require authentication
- **Facility Isolation**: Users can only access data from their own facility
- **Password Hashing**: Bcrypt with automatic salt generation
- **HTTPS Required**: For production deployment
- **CORS Configuration**: Configurable allowed origins

## Example API Usage

### Register New Facility

```bash
curl -X POST "http://localhost:8000/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@facility.com",
    "password": "SecurePass123!",
    "full_name": "Jane Smith",
    "facility_name": "Sunrise Care Center",
    "facility_license_number": "SNF-12345",
    "facility_bed_count": 120
  }'
```

### Login

```bash
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@facility.com&password=SecurePass123!"
```

### Create Risk Assessment

```bash
curl -X POST "http://localhost:8000/api/v1/assessments/" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "resident_id": 1,
    "assessment_type": "falls",
    "risk_factors": {
      "history_of_falls": true,
      "mobility_impairment": true,
      "psychotropic_medications": false,
      "cognitive_impairment": true,
      "age": 87,
      "poor_lighting": false
    }
  }'
```

### Generate Care Plan

```bash
curl -X POST "http://localhost:8000/api/v1/assessments/care-plan" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "assessment_id": 1
  }'
```

## Database Migrations

Using Alembic for database migrations:

```bash
# Create a new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1
```

## Development

### Running Tests

```bash
pytest
```

### Code Formatting

```bash
black app/
isort app/
```

### Type Checking

```bash
mypy app/
```

## Production Considerations

1. **Database Connection Pooling**: Configure SQLAlchemy pool size for production load
2. **Rate Limiting**: Implement rate limiting for API endpoints
3. **Monitoring**: Set up application monitoring (e.g., Sentry, DataDog)
4. **Logging**: Configure structured logging for production
5. **Backup**: Set up automated database backups
6. **SSL/TLS**: Ensure HTTPS is enforced
7. **Environment Variables**: Never commit .env file to version control

## Support

For issues or questions:
- Email: support@qapishield.com
- Documentation: https://docs.qapishield.com

## License

Proprietary - QAPIShield™ 2024
