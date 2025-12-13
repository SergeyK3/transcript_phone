import unittest
from hello import greet_user

class TestGreetUser(unittest.TestCase):
    def test_greet_user(self):
        self.assertEqual(greet_user("Сергей"), "Привет, Сергей!")
        self.assertEqual(greet_user("Анна"), "Привет, Анна!")
        self.assertNotEqual(greet_user("Дмитрий"), "Hello, Дмитрий!")  # Проверка на неверный ответ

if __name__ == "__main__":
    unittest.main()