from sqlmodel import Session, select
from app.database import engine, create_db_and_tables
from app.models import User
from app.enums import Role
from app.security import hash_password


def create_admin():
    create_db_and_tables()
    with Session(engine) as session:
        existing_admin = session.exec(
            select(User).where(User.role == Role.admin)
        .first()
        )
        if existing_admin:
            print("Admin already exists!")
            return

        admin_user = User(
            username="admin",
            email="admin@bookstore.com",
            hashed_password=hash_password("AdminPassword123!"),
            role=Role.admin,
            is_active=True,
        )
        session.add(admin_user)
        session.commit()
        print("Admin user created successfully!")


if __name__ == "__main__":
    create_admin()