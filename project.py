from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from typing import List, Optional
from datetime import datetime, timedelta, timezone
import bcrypt
import jwt

# ─────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────

SECRET_KEY = "zalupa228_super_secret_jwt_key_32bytes"
ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = 30
ADMIN_EMAIL = "martin.shahinyan2008@gmail.com"

# ─────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────

engine = create_engine("sqlite:///books.db")
Base = declarative_base()
sessionLocal = sessionmaker(bind=engine)

def get_db():
    db = sessionLocal()
    try:
        yield db
    finally:
        db.close()

# ─────────────────────────────────────────
# SQL TABLES
# ─────────────────────────────────────────

class UserTable(Base):
    __tablename__ = "users"
    id = Column(Integer, autoincrement=True, primary_key=True)
    name = Column(String)
    surname = Column(String)
    gmail = Column(String, unique=True)
    password = Column(String)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class BookTable(Base):
    __tablename__ = "books"
    id = Column(Integer, autoincrement=True, primary_key=True)
    author = Column(String)
    year = Column(Integer)
    name = Column(String)
    price = Column(Integer)
    added_by = Column(String)  

class ActionLog(Base):
    __tablename__ = "logs"
    id = Column(Integer, autoincrement=True, primary_key=True)
    user_gmail = Column(String)
    action = Column(String)  
    detail = Column(String) 
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))

Base.metadata.create_all(engine)

# SQLite schema migration helper
with engine.connect() as conn:
    inspector = inspect(engine)
    columns = [col['name'] for col in inspector.get_columns('books')]
    if 'added_by' not in columns:
        conn.execute(text("ALTER TABLE books ADD COLUMN added_by VARCHAR;"))
        conn.commit()

# ─────────────────────────────────────────
# PYDANTIC СХЕМЫ
# ─────────────────────────────────────────

class UserRegister(BaseModel):
    name: str = Field(..., min_length=2, max_length=20)
    surname: str = Field(..., min_length=2, max_length=20)
    gmail: EmailStr
    password: str = Field(..., min_length=4)

class UserLogin(BaseModel):
    gmail: EmailStr
    password: str = Field(..., min_length=4)

class BookCreate(BaseModel):
    author: str = Field(..., min_length=2)
    year: int = Field(..., gt=0, le=2026)
    name: str = Field(..., min_length=2)
    price: int = Field(..., gt=0)

class BookUpdate(BaseModel):
    author: Optional[str] = Field(None, min_length=2)
    year: Optional[int] = Field(None, gt=0, le=2026)
    name: Optional[str] = Field(None, min_length=2)
    price: Optional[int] = Field(None, gt=0)
    new_author: Optional[str] = Field(None, min_length=2)
    new_year: Optional[int] = Field(None, gt=0, le=2026)
    new_name: Optional[str] = Field(None, min_length=2)
    new_price: Optional[int] = Field(None, gt=0)

class BookResponse(BookCreate):
    id: int
    added_by: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

# ─────────────────────────────────────────
# HASHING
# ─────────────────────────────────────────

def hash_password(password: str) -> str:
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode('utf-8')

def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode('utf-8'), hashed.encode('utf-8'))
    except Exception:
        return False

# ─────────────────────────────────────────
# JWT
# ─────────────────────────────────────────

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/user/login")

def create_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    payload = decode_token(token)
    user = db.query(UserTable).filter(UserTable.gmail == payload.get("gmail")).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

def get_admin_user(current_user: UserTable = Depends(get_current_user)):
    if current_user.gmail != ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail="Admin only")
    return current_user

# ─────────────────────────────────────────
# HELPER 
# ─────────────────────────────────────────

def log_action(db: Session, user_gmail: str, action: str, detail: str):
    entry = ActionLog(user_gmail=user_gmail, action=action, detail=detail)
    db.add(entry)
    db.commit()

# ─────────────────────────────────────────
# APP
# ─────────────────────────────────────────

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────
# USER ENDPOINTS
# ─────────────────────────────────────────

@app.post("/user/create")
def create_user(user_in: UserRegister, db: Session = Depends(get_db)):
    existing = db.query(UserTable).filter(UserTable.gmail == user_in.gmail).first()
    if existing:
        raise HTTPException(status_code=400, detail="User with this email already exists")
    new_user = UserTable(**user_in.model_dump())
    new_user.password = hash_password(user_in.password)
    new_user.is_admin = (user_in.gmail == ADMIN_EMAIL)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    log_action(db, user_in.gmail, "register", f"{user_in.name} {user_in.surname} registered")
    return {"message": "User created", "name": new_user.name}

@app.post("/user/login")
def login_user(user_in: UserLogin, db: Session = Depends(get_db)):
    user = db.query(UserTable).filter(UserTable.gmail == user_in.gmail).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not verify_password(user_in.password, user.password):
        raise HTTPException(status_code=401, detail="Wrong password")
    token = create_token({"id": user.id, "gmail": user.gmail})
    log_action(db, user.gmail, "login", f"{user.name} logged in")
    return {
        "message": "Login confirmed",
        "token": token,
        "is_admin": user.is_admin,
        "name": user.name
    }

@app.get("/user/me")
def get_me(current_user: UserTable = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "name": current_user.name,
        "surname": current_user.surname,
        "gmail": current_user.gmail,
        "is_admin": current_user.is_admin,
        "created_at": current_user.created_at
    }

# ─────────────────────────────────────────
# ADMIN ENDPOINTS
# ─────────────────────────────────────────

@app.get("/admin/users")
def get_all_users(admin: UserTable = Depends(get_admin_user), db: Session = Depends(get_db)):
    users = db.query(UserTable).all()
    return [{
        "id": u.id,
        "name": u.name,
        "surname": u.surname,
        "gmail": u.gmail,
        "is_admin": u.is_admin,
        "created_at": u.created_at
    } for u in users]

@app.get("/admin/logs")
def get_logs(admin: UserTable = Depends(get_admin_user), db: Session = Depends(get_db)):
    logs = db.query(ActionLog).order_by(ActionLog.timestamp.desc()).all()
    return [{
        "id": l.id,
        "user": l.user_gmail,
        "action": l.action,
        "detail": l.detail,
        "time": l.timestamp
    } for l in logs]

@app.delete("/admin/users/{user_id}")
def delete_user(user_id: int, admin: UserTable = Depends(get_admin_user), db: Session = Depends(get_db)):
    user = db.query(UserTable).filter(UserTable.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.gmail == ADMIN_EMAIL:
        raise HTTPException(status_code=400, detail="Cannot delete admin")
    db.delete(user)
    db.commit()
    log_action(db, admin.gmail, "delete_user", f"Deleted user {user.gmail}")
    return {"message": "User deleted"}

# ─────────────────────────────────────────
# BOOK ENDPOINTS
# ─────────────────────────────────────────

@app.post("/addbook")
def add_book(book_in: BookCreate, db: Session = Depends(get_db), current_user: UserTable = Depends(get_current_user)):
    new_book = BookTable(**book_in.model_dump(), added_by=current_user.gmail)
    db.add(new_book)
    db.commit()
    db.refresh(new_book)
    log_action(db, current_user.gmail, "add_book", f"Added '{book_in.name}' by {book_in.author}")
    return {"message": "Book added", "book": BookResponse.model_validate(new_book)}

@app.get("/books", response_model=List[BookResponse])
def all_books(db: Session = Depends(get_db)):
    books = db.query(BookTable).all()
    return books

@app.get("/books/{id}", response_model=BookResponse)
def book_by_id(id: int, db: Session = Depends(get_db)):
    book = db.query(BookTable).filter(BookTable.id == id).first()
    if not book:
        raise HTTPException(status_code=404, detail="No book with this id")
    return book

@app.put("/books/update/{id}", response_model=BookResponse)
def update_book(
    id: int, 
    new_author: Optional[str] = None, 
    new_year: Optional[int] = None, 
    new_name: Optional[str] = None, 
    new_price: Optional[int] = None, 
    book_in: Optional[BookUpdate] = None,
    db: Session = Depends(get_db), 
    current_user: UserTable = Depends(get_current_user)
):
    book = db.query(BookTable).filter(BookTable.id == id).first()
    if not book:
        raise HTTPException(status_code=404, detail="No book with this id")
    
    author = (book_in.author or book_in.new_author if book_in else None) or new_author
    year = (book_in.year or book_in.new_year if book_in else None) or new_year
    name = (book_in.name or book_in.new_name if book_in else None) or new_name
    price = (book_in.price or book_in.new_price if book_in else None) or new_price

    if author is not None:
        book.author = author
    if year is not None:
        book.year = year
    if name is not None:
        book.name = name
    if price is not None:
        book.price = price

    db.commit()
    db.refresh(book)
    log_action(db, current_user.gmail, "update_book", f"Updated book id={id} to '{book.name}'")
    return book

@app.patch("/books/update/some/{id}", response_model=BookResponse)
def update_some_book(
    id: int, 
    new_author: Optional[str] = None, 
    new_year: Optional[int] = None, 
    new_name: Optional[str] = None, 
    new_price: Optional[int] = None, 
    book_in: Optional[BookUpdate] = None,
    db: Session = Depends(get_db), 
    current_user: UserTable = Depends(get_current_user)
):
    book = db.query(BookTable).filter(BookTable.id == id).first()
    if not book:
        raise HTTPException(status_code=404, detail="No book with this id")

    author = (book_in.author or book_in.new_author if book_in else None) or new_author
    year = (book_in.year or book_in.new_year if book_in else None) or new_year
    name = (book_in.name or book_in.new_name if book_in else None) or new_name
    price = (book_in.price or book_in.new_price if book_in else None) or new_price

    if author is not None:
        book.author = author
    if year is not None:
        book.year = year
    if name is not None:
        book.name = name
    if price is not None:
        book.price = price

    db.commit()
    db.refresh(book)
    log_action(db, current_user.gmail, "update_book", f"Partially updated book id={id}")
    return book

@app.delete("/books/delete/{id}")
def delete_book(id: int, db: Session = Depends(get_db), current_user: UserTable = Depends(get_current_user)):
    book = db.query(BookTable).filter(BookTable.id == id).first()
    if not book:
        raise HTTPException(status_code=404, detail="No book with this id")
    db.delete(book)
    db.commit()
    log_action(db, current_user.gmail, "delete_book", f"Deleted book id={id} '{book.name}'")
    return {"message": "Book deleted", "id": id}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("project:app", host="127.0.0.1", port=8000, reload=True)