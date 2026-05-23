from fastapi import FastAPI, BackgroundTasks

app = FastAPI()

def get_text(email: str, message = "hi {name}"):
    with open("log.txt", mode= "a") as email_file:
        contect = f"message for {email}: {message} "
        email_file.write(contect)

@app.post("/user/create")
def create_user(name: str, age: int, my_email:str, background_tasj : BackgroundTasks):
    background_tasj.add_task(get_text, my_email, message=f"hi {name}, how are you?")
    return {"name":name,
            "age": age,
            "message sended to email": my_email}