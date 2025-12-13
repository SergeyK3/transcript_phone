def greet_user(name):
    return f"Привет, {name}!"

if __name__ == "__main__":
    # Тест функции
    username = input("Введите ваше имя: ")
    print(greet_user(username))  # Вывод приветствия