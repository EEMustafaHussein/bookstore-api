"""Creates the shop owner account, or resets its password.

    python create_owner.py
    python create_owner.py --email you@example.com --name "اسمك"
"""

import argparse
import getpass
import sys

from sqlmodel import Session, select

from app.database import create_db_and_tables, engine
from app.enums import Role
from app.forms import email as normalize_email
from app.models import User
from app.security import hash_password, password_problem


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or update the owner account")
    parser.add_argument("--email")
    parser.add_argument("--name", default="")
    parser.add_argument("--password", help="omit to type it safely")
    args = parser.parse_args()

    email = normalize_email(args.email or input("البريد الإلكتروني: ").strip())
    if not email:
        print("البريد الإلكتروني غير صحيح")
        return 1
    name = args.name or input("الاسم: ").strip() or "صاحب المتجر"
    password = args.password or getpass.getpass("كلمة المرور: ")
    problem = password_problem(password)
    if problem:
        print(problem)
        return 1
    if not args.password and getpass.getpass("أعد كتابة كلمة المرور: ") != password:
        print("كلمتا المرور غير متطابقتين")
        return 1

    create_db_and_tables()
    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == email)).first()
        if user is None:
            user = User(name=name, email=email, hashed_password=hash_password(password))
        else:
            user.hashed_password = hash_password(password)
            if args.name:
                user.name = name
        user.role = Role.owner
        user.is_active = True
        session.add(user)
        session.commit()
    print(f"تم! حساب المالك جاهز: {email}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
