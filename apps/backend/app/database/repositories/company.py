from uuid import UUID

from sqlalchemy.orm import Session

from app.models.company import Company


def create_company(session: Session, legal_name: str, **fields: str | None) -> Company:
    company = Company(legal_name=legal_name, **fields)
    session.add(company)
    session.flush()
    return company


def get_company(session: Session, company_id: UUID) -> Company | None:
    return session.get(Company, company_id)
