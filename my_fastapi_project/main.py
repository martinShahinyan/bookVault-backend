from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker, declarative_base, Session


engine = create_engine("sqlite:///main.db")
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, autoincrement = True, primary_key = True)
    name = Column(String)
    surname = Column(String)
    age = Column(Integer)

Base.metadata.create_all(engine)
sessionLocal = sessionmaker(bind=engine)

def get_db():
    db = sessionLocal()
    try:
        yield db
    finally:
        db.close()

app = FastAPI()


def notification(email: str, message = ""):
    with open ("log.txt", mode ="a") as email_file:
        content = f"notification for {email}: {message}"
        email_file.write(content)

@app.post("/create/user")
def create_user(new_name:str, new_surname:str, new_age:int, my_email: str, background_task: BackgroundTasks, db: Session = Depends(get_db)):
    new_user = User(name = new_name, surname = new_surname, age= new_age)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    background_task.add_task(notification, my_email, message = f"hi {new_name}")
    return {"Message":"new user added",
            "id":new_user.id,
            "name":new_name,
            "surname":new_surname,
            "age":new_age,
            "we send message to":my_email}


@app.get("/users")
def all_users(db: Session = Depends(get_db)):
    users = db.query(User).all()
    if not users:
        raise HTTPException (status_code=404, detail="not users in data")
    return [{"id":u.id,
            "name":u.name,
            "surname":u.surname,
            "age":u.age} for u in users]



@app.get("/users/{id}")
def get_user_id(id:int, db : Session = Depends(get_db)):
    user = db.query(User).filter(User.id == id).first()
    if not user:
        raise HTTPException(status_code=404, detail="not user in data")
    return {
        "id":user.id,
        "name":user.name,
        "surname":user.surname,
        "age":user.age
    }

@app.delete("/users/delete/{id}")
def delete_user(id:int, db : Session = Depends(get_db)):
    user = db.query(User).filter(User.id == id).first()
    if not user:
        raise HTTPException(status_code=404, detail="not user in data")
    db.delete(user)
    db.commit()
    return {"Message":"User deleted",
            "id": user.id,
            "name" : user.name,
            "surname":user.surname,
            "age":user.age}

@app.put("/users/update/{id}")
def update_user(id:int, new_name:str, new_surname:str, new_age:int, db : Session = Depends(get_db)):
    user_update = db.query(User).filter(User.id == id).first()
    if not user_update:
        raise HTTPException(status_code=404, detail="not user in data")
    user_update.name = new_name
    user_update.surname = new_surname
    user_update.age = new_age
    db.commit()
    db.refresh(user_update)
    return user_update

@app.patch("/users/update/some/{id}")
def users_some_update(id:int, new_name:str = None, new_surname:str = None, new_age: int = None, db : Session = Depends(get_db)):
    user = db.query(User).filter(User.id == id).first()
    if not user:
        raise HTTPException(status_code=404, detail="not user in data")
    if new_name is not None:
        user.name = new_name
    if new_surname is not None:
        user.surname = new_surname
    if new_age is not None:
        user.age = new_age
    db.commit()
    db.refresh(user)
    return user

