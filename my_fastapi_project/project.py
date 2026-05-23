from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from pydantic import BaseModel, Field
from typing import Annotated, List

engine = create_engine("sqlite:///books.db")
Base = declarative_base()

class Book(Base):
    __tablename__ = "books"
    id = Column(Integer, autoincrement=True, primary_key=True)
    author = Column(String)
    year = Column(Integer)
    name = Column(String)
    price = Column(Integer)

Base.metadata.create_all(engine)
sessionLocal = sessionmaker(bind=engine)

class BookCreate(BaseModel):
    author: str = Field(..., min_length=2)
    year: int = Field(..., gt=0, lt=2026)
    name: str = Field(..., min_length=2)
    price: int = Field(..., gt=0)

def get_db():
    db = sessionLocal()
    try:
        yield db
    finally:
        db.close()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/addbook")
def add_book(book_in : BookCreate, db : Session = Depends(get_db)):
    new_book = Book(**book_in.model_dump())
    db.add(new_book)
    db.commit()
    db.refresh(new_book)
    return {"message":"book added",
            "book":new_book}


class BookResponse(BookCreate):
    id:int
    class Conf:
        from_attributes = True

@app.get("/books", response_model = List[BookResponse])
def all_books(db : Session = Depends(get_db)):
    books = db.query(Book).all()
    if not books:
        raise HTTPException(status_code=404, detail="no book in base")
    return books

@app.get("/books/{id}")
def book_by_id(id:int, db : Session = Depends(get_db)):
    book = db.query(Book).filter(Book.id == id).first()
    if not book:
        raise HTTPException(status_code=404, detail="no book with this id")
    return book

@app.put("/books/update/{id}")
def update_book(id:int, new_author:str, new_year:int, new_name  : str, new_price:int, db : Session = Depends(get_db)):
    updated_book = db.query(Book).filter(Book.id == id).first()
    if not updated_book:
        raise HTTPException(status_code=404, detail="no book with this id")
    updated_book.author = new_author
    updated_book.year = new_year
    updated_book.name = new_name
    updated_book.price = new_price
    db.commit()
    db.refresh(updated_book)
    return updated_book

@app.patch("/books/update/some/{id}")
def update_some_book(id:int, new_author:str = None, new_year: int = None, new_name: str = None, new_price: int = None, db : Session = Depends(get_db)):
    book = db.query(Book).filter(Book.id == id).first()
    if not book:
        raise HTTPException(status_code=404, detail="no book with this id")
    if new_author is not None:
        book.author = new_author
    if new_year is not None:
        book.year = new_year
    if new_name is not None:
        book.name = new_name
    if new_price is not None:
        book.price = new_price
    db.commit()
    db.refresh(book)
    return book

@app.delete("/books/delete/{id}")
def delete_book(id:int, db : Session = Depends(get_db)):
    book = db.query(Book).filter(Book.id == id).first()
    if not book:
        raise HTTPException(status_code=404, detail="no book with this id")
    db.delete(book)
    db.commit()
    return book